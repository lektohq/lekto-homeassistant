"""The event entity of the Lekto integration: a document came in, was filed, needs a look."""

from typing import TYPE_CHECKING, Final, override

from homeassistant.components.event import EventEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .capabilities import Capability
from .entity import LektoEntity
from .stream import signal

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from pylekto.models import EventMessage

    from .coordinator import LektoConfigEntry, LektoCoordinator

# Only what Lekto's event holds goes on; titles, contacts and types stay in Lekto.
EVENT_TYPES: Final = {
    "document.received": "received",
    "document.filed": "filed",
    "document.review_required": "review_required",
}
# Lekto asks for a review only of uncertain (yellow) or failed (red) documents.
LANES: Final = frozenset({"yellow", "red"})


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: LektoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the instance's document event, if the token may follow the household's documents."""
    if Capability.EVENTS in entry.runtime_data.capabilities:
        async_add_entities([LektoDocumentEvent(entry.runtime_data)])


class LektoDocumentEvent(LektoEntity, EventEntity):
    """What happened last to one of the household's documents."""

    _attr_translation_key = "document"
    _attr_event_types = list(EVENT_TYPES.values())

    def __init__(self, coordinator: LektoCoordinator) -> None:
        """Make the document event of the instance."""
        super().__init__(coordinator, "document")

    @property
    @override
    def available(self) -> bool:
        """Stay available while the numbers fail: the events come on their own stream."""
        return True

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Keep the last event; a new count of the numbers changes nothing here."""

    @override
    async def async_added_to_hass(self) -> None:
        """Take the events of the entry's stream."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal(self.coordinator.config_entry), self._handle_event
            )
        )

    @callback
    def _handle_event(self, event: EventMessage) -> None:
        """Lekto sends every event on one stream; only three are worth an automation."""
        event_type = EVENT_TYPES.get(event.type)
        if event_type is None:
            return
        attributes: dict[str, str] = {}
        if event.document_id is not None:
            attributes["document_id"] = str(event.document_id)
        lane = (event.model_extra or {}).get("lane")
        if lane in LANES:
            attributes["lane"] = lane
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
