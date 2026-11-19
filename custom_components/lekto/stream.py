"""The event stream of the Lekto integration: what happens to documents, as it happens."""

import logging
from asyncio import sleep
from time import monotonic
from typing import TYPE_CHECKING, Final

from homeassistant.helpers.dispatcher import async_dispatcher_send
from pylekto import (
    LektoAuthenticationError,
    LektoError,
    LektoForbiddenError,
    LektoRateLimitError,
)

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pylekto.models import EventMessage

    from .coordinator import LektoConfigEntry

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


async def listen(hass: HomeAssistant, entry: LektoConfigEntry) -> None:
    """Listen to Lekto's events until the entry unloads, connecting again when the stream ends.

    Lekto sends no events missed while the stream was down, so the numbers are fetched again
    before each new connection.
    """
    coordinator = entry.runtime_data
    retry = RETRY_FIRST
    lost = False
    while True:
        opened = monotonic()
        try:
            async for event in coordinator.client.events.listen():
                if lost:
                    _LOGGER.info("The event stream is back")
                    lost = False
                _handle(hass, entry, event)
        except LektoAuthenticationError, LektoForbiddenError:
            entry.async_start_reauth(hass)
            return
        except LektoRateLimitError as err:
            retry = max(retry, err.retry_after or 0)
        except LektoError as err:
            if not lost:
                _LOGGER.info("Lost the event stream, connecting again: %s", err)
                lost = True
        # A connection that held a while worked; only quick failures wait longer each time.
        if monotonic() - opened > RETRY_FIRST:
            retry = RETRY_FIRST
        await sleep(retry)
        retry = min(retry * 2, RETRY_LAST)
        await coordinator.async_request_refresh()


def _handle(hass: HomeAssistant, entry: LektoConfigEntry, event: EventMessage) -> None:
    """Every event goes out, so that entities need no stream of their own."""
    async_dispatcher_send(hass, signal(entry), event)
    if event.type in COUNTED:
        entry.async_create_task(hass, entry.runtime_data.async_request_refresh())
