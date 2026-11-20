"""The event entity of the Lekto integration: a document came in, was filed, needs a look."""

import asyncio
import logging
from typing import TYPE_CHECKING, Final, override

from homeassistant.components.event import EventEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from pylekto import LektoError

from .capabilities import Capability
from .const import CONF_EVENT_FIELDS, EVENT_FIELDS
from .entity import LektoEntity
from .names import FIELD_KINDS, Kind
from .stream import signal

if TYPE_CHECKING:
    from collections.abc import Collection
    from uuid import UUID

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from pylekto.models import EventMessage

    from .coordinator import LektoConfigEntry, LektoCoordinator
    from .names import LektoNames

_LOGGER = logging.getLogger(__name__)

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
    # Titles and names stay out of the recorder's history: privacy first.
    _unrecorded_attributes = frozenset(EVENT_FIELDS)

    def __init__(self, coordinator: LektoCoordinator) -> None:
        """Make the document event of the instance."""
        super().__init__(coordinator, "document")
        # Events wait for their document's fields one after the other, so they stay in order.
        self._order = asyncio.Lock()

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
        # A background task, so that unloading cancels events still waiting for their fields.
        entry = self.coordinator.config_entry
        entry.async_create_background_task(self.hass, self._trigger(event, event_type), "event")

    async def _trigger(self, event: EventMessage, event_type: str) -> None:
        async with self._order:
            attributes: dict[str, str | list[str]] = {}
            if event.document_id is not None:
                attributes["document_id"] = str(event.document_id)
                wanted = self.coordinator.config_entry.options.get(CONF_EVENT_FIELDS, [])
                if wanted:
                    attributes |= await document_fields(self.coordinator, event.document_id, wanted)
            lane = (event.model_extra or {}).get("lane")
            if lane in LANES:
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
    names = coordinator.names
    fields: dict[str, str | list[str]] = {}
    if "title" in wanted:
        fields["title"] = document.title
    if "document_date" in wanted and document.document_date is not None:
        fields["document_date"] = document.document_date.isoformat()
    item_ids = {
        "contact": document.contact_id,
        "document_type": document.document_type_id,
        "space": document.space_id,
    }
    for field, item_id in item_ids.items():
        kind = FIELD_KINDS[field]
        if field in wanted and item_id is not None and names.may(kind):
            name = await _name(names, kind, item_id)
            if name is not None:
                fields[field] = name
    if "tags" in wanted and names.may(Kind.TAG):
        tags = [await _name(names, Kind.TAG, tag_id) for tag_id in document.tag_ids]
        fields["tags"] = [tag for tag in tags if tag is not None]
    return fields


async def _name(names: LektoNames, kind: Kind, item_id: UUID) -> str | None:
    """Leave out a name Lekto cannot give now, rather than fail the event."""
    try:
        return await names.name(kind, item_id)
    except LektoError:
        return None
