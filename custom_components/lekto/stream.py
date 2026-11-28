"""The event stream of the Lekto integration: what happens to documents, as it happens."""

import logging
from asyncio import sleep
from time import monotonic
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


def connection_signal(entry: LektoConfigEntry) -> str:
    """Return the dispatcher signal that goes out when the entry's stream is lost or flows again."""
    return f"{DOMAIN}_{entry.entry_id}_stream"


class LektoStream:
    """Lekto's events of one entry: passed on as they come, the stream connected again when lost."""

    def __init__(self, coordinator: LektoCoordinator) -> None:
        """Start without a connection; ``listen`` makes it."""
        self._coordinator = coordinator
        self._retry = RETRY_FIRST
        self._lost = False
        self._since = 0.0
        self.connected = False

    async def listen(self) -> None:
        """Listen to Lekto's events until the entry unloads, connecting again when the stream ends.

        Lekto sends no events missed while the stream was down, so the numbers are fetched again
        before each new connection.
        """
        try:
            await self._listen()
        except Exception:
            # A bug ends the listening for good; the entity must not go on promising events.
            self._lose("an unexpected error")
            raise

    async def _listen(self) -> None:
        coordinator = self._coordinator
        while True:
            try:
                async for event in coordinator.client.events.listen(on_connected=self._flows):
                    self._handle(event)
            except LektoAuthenticationError as err:
                self._lose(err)
                coordinator.config_entry.async_start_reauth(coordinator.hass)
                return
            except LektoForbiddenError as err:
                self._lose(err)
                await coordinator.reload_if_rights_changed()
            except LektoRateLimitError as err:
                self._lose(err)
                self._retry = max(self._retry, err.retry_after or 0)
            except LektoError as err:
                self._lose(err)
            else:
                self._lose("Lekto ended it")
            await sleep(self._retry)
            self._retry = min(self._retry * 2, RETRY_LAST)
            await coordinator.async_request_refresh()

    @callback
    def _flows(self) -> None:
        """Take pylekto's sign that the stream flows: an answer alone would not show it."""
        self._since = monotonic()
        if self._lost:
            _LOGGER.info("The event stream is back")
            self._lost = False
        self._set_connected(connected=True)

    def _lose(self, reason: object) -> None:
        """One line in the log for each loss, however many tries it takes to come back."""
        # Only a stream that flowed a while worked; one that breaks off at once waits longer.
        if self.connected and monotonic() - self._since > RETRY_FIRST:
            self._retry = RETRY_FIRST
        if not self._lost:
            _LOGGER.info("Lost the event stream: %s", reason)
            self._lost = True
        self._set_connected(connected=False)

    def _set_connected(self, *, connected: bool) -> None:
        """Only a change goes out: a stream that is lost stays lost through every failed try."""
        if connected == self.connected:
            return
        self.connected = connected
        coordinator = self._coordinator
        async_dispatcher_send(coordinator.hass, connection_signal(coordinator.config_entry))

    def _handle(self, event: EventMessage) -> None:
        """Every event goes out, so that entities need no stream of their own."""
        coordinator = self._coordinator
        entry = coordinator.config_entry
        async_dispatcher_send(coordinator.hass, signal(entry), event)
        if event.type in COUNTED:
            entry.async_create_task(coordinator.hass, coordinator.async_request_refresh())
