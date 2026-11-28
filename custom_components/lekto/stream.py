"""The event stream of the Lekto integration: what happens to documents, as it happens."""

import logging
from asyncio import sleep
from typing import TYPE_CHECKING, Final

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pylekto import (
    LektoAuthenticationError,
    LektoError,
    LektoForbiddenError,
    LektoRateLimitError,
)

from .const import DOMAIN

if TYPE_CHECKING:
    from pylekto.models import EventMessage

    from .coordinator import LektoConfigEntry, LektoCoordinator

_LOGGER = logging.getLogger(__name__)

RETRY_FIRST: Final = 5.0
RETRY_LAST: Final = 300.0

# Moves count too: a document may be new to the editors of the space it moved to.
COUNTED: Final = frozenset(
    {
        "document.received",
        "document.filed",
        "document.review_required",
        "document.lane_changed",
        "document.confirmed",
        "document.moved",
        "document.deleted",
    }
)


def signal(entry: LektoConfigEntry) -> str:
    """Return the dispatcher signal the entry's events go out on."""
    return f"{DOMAIN}_{entry.entry_id}_event"


class LektoStream:
    """Lekto's events of one entry: passed on as they come, the stream connected again when lost."""

    def __init__(self, coordinator: LektoCoordinator) -> None:
        """Start without a connection; ``listen`` makes it."""
        self._coordinator = coordinator
        self._retry = RETRY_FIRST

    async def listen(self) -> None:
        """Listen to Lekto's events until the entry unloads, connecting again when the stream ends.

        Lekto sends no events missed while the stream was down, so the numbers are fetched again
        before each new connection.
        """
        coordinator = self._coordinator
        lost = False
        while True:
            try:
                async for event in coordinator.client.events.listen(on_connected=self._flows):
                    if lost:
                        _LOGGER.info("The event stream is back")
                        lost = False
                    self._handle(event)
            except LektoAuthenticationError:
                coordinator.config_entry.async_start_reauth(coordinator.hass)
                return
            except LektoForbiddenError as err:
                await coordinator.reload_if_rights_changed()
                if not lost:
                    _LOGGER.info("Lost the event stream, connecting again: %s", err)
                    lost = True
            except LektoRateLimitError as err:
                self._retry = max(self._retry, err.retry_after or 0)
            except LektoError as err:
                if not lost:
                    _LOGGER.info("Lost the event stream, connecting again: %s", err)
                    lost = True
            await sleep(self._retry)
            self._retry = min(self._retry * 2, RETRY_LAST)
            await coordinator.async_request_refresh()

    @callback
    def _flows(self) -> None:
        """Only a stream that flows starts the wait short again, not one that merely answered."""
        self._retry = RETRY_FIRST

    def _handle(self, event: EventMessage) -> None:
        """Every event goes out, so that entities need no stream of their own."""
        coordinator = self._coordinator
        entry = coordinator.config_entry
        async_dispatcher_send(coordinator.hass, signal(entry), event)
        if event.type in COUNTED:
            entry.async_create_task(coordinator.hass, coordinator.async_request_refresh())
