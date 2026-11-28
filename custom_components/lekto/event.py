"""The event entity of the Lekto integration: a document came in, was filed, needs a look."""

import asyncio
import logging
from typing import TYPE_CHECKING, Final, override

from homeassistant.components.event import EventEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from pylekto import LektoError

from .capabilities import Capability
from .const import CONF_EVENT_FIELDS, EVENT_FIELDS, LANES
from .entity import LektoEntity
from .names import document_names
from .stream import connection_signal, signal

if TYPE_CHECKING:
    from collections.abc import Collection
    from uuid import UUID

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from pylekto.models import EventMessage

    from .coordinator import LektoConfigEntry, LektoCoordinator

_LOGGER = logging.getLogger(__name__)

# Lekto's stream pushes the events; the entity never polls.
PARALLEL_UPDATES = 0

EVENT_TYPES: Final = {
    "document.received": "received",
    "document.filed": "filed",
    "document.review_required": "review_required",
}
# Lekto asks for a review only of uncertain (yellow) or failed (red) documents.
REVIEW_LANES: Final = frozenset(LANES) - {"green"}


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: LektoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the instance's document event, if the token may follow the household's documents."""
    if Capability.EVENTS in entry.runtime_data.capabilities:
        async_add_entities([LektoDocumentEvent(entry)])


class LektoDocumentEvent(LektoEntity, EventEntity):
    """What happened last to one of the household's documents."""

    _attr_translation_key = "document"
    _attr_event_types = list(EVENT_TYPES.values())
    # Titles and names stay out of the recorder's history: privacy first.
    _unrecorded_attributes = frozenset(EVENT_FIELDS)

    def __init__(self, entry: LektoConfigEntry) -> None:
        """Make the document event of the entry's instance."""
        super().__init__(entry.runtime_data, "document")
        self._entry = entry
        # Events wait for their document's fields one after the other, so they stay in order.
        self._order = asyncio.Lock()

    @property
    @override
    def available(self) -> bool:
        """Follow the stream, not the numbers: the events come on a connection of their own."""
        return self._entry.runtime_data.stream.connected

    @override
    async def async_added_to_hass(self) -> None:
        """Take the events of the entry's stream, and follow whether it flows."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal(self._entry), self._handle_event)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, connection_signal(self._entry), self.async_write_ha_state
            )
        )

    @callback
    def _handle_event(self, event: EventMessage) -> None:
        """Lekto sends every event on one stream; only three are worth an automation."""
        event_type = EVENT_TYPES.get(event.type)
        if event_type is None:
            return
        # A background task, so that unloading cancels events still waiting for their fields.
        self._entry.async_create_background_task(
            self.hass, self._trigger(event, event_type), "event"
        )

    async def _trigger(self, event: EventMessage, event_type: str) -> None:
        async with self._order:
            attributes: dict[str, str | list[str]] = {}
            if event.document_id is not None:
                attributes["document_id"] = str(event.document_id)
                wanted = self._entry.options.get(CONF_EVENT_FIELDS, [])
                if wanted:
                    attributes |= await document_fields(
                        self._entry.runtime_data, event.document_id, wanted
                    )
            # Read as an attribute: it is one whether pylekto's model names the lane or not.
            lane = getattr(event, "lane", None)
            if lane in REVIEW_LANES:
                attributes["lane"] = lane
            self._trigger_event(event_type, attributes)
            self.async_write_ha_state()


async def document_fields(
    coordinator: LektoCoordinator, document_id: UUID, wanted: Collection[str]
) -> dict[str, str | list[str]]:
    """Return the ``wanted`` fields of a document; one Lekto cannot give is left out."""
    try:
        document = await coordinator.client.documents.get(document_id)
    except LektoError as err:
        _LOGGER.debug("Could not fetch the fields of document %s: %s", document_id, err)
        return {}
    fields: dict[str, str | list[str]] = {}
    if "title" in wanted:
        fields["title"] = document.title
    if "document_date" in wanted and document.document_date is not None:
        fields["document_date"] = document.document_date.isoformat()
    single, tags = await document_names(coordinator.names, document, wanted)
    fields |= {field: name for field, name in single.items() if name is not None}
    if tags is not None:
        fields["tags"] = tags
    return fields
