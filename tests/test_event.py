"""The document event: what happened last to one of the household's documents."""

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, State, callback
from homeassistant.helpers.event import async_track_state_change_event
from pylekto import LektoConnectionError
from pylekto.models import EventMessage
from pytest_homeassistant.common import mock_restore_cache_with_extra_data

from custom_components.lekto.const import CONF_EVENT_FIELDS, EVENT_FIELDS
from custom_components.lekto.event import LektoDocumentEvent, document_fields

from .const import DOCUMENT_ID, document, event, me, streams

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry

pytestmark = pytest.mark.stream

ENTITY_ID = "event.lekto_document"


async def _set_up(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_no_event_yet(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Before any event the entity offers the three kinds and has no state."""
    lekto.events.listen.side_effect = streams([])

    await _set_up(hass, config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["event_types"] == ["received", "filed", "review_required"]
    assert await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (event("document.received"), ("received", {"document_id": DOCUMENT_ID})),
        (
            event("document.filed", space_id="0195f3c2-7a10-7c4e-9b1d-2f6a8e4c1f00"),
            ("filed", {"document_id": DOCUMENT_ID}),
        ),
        (
            event("document.review_required", lane="red"),
            ("review_required", {"document_id": DOCUMENT_ID, "lane": "red"}),
        ),
        (
            event("document.review_required", lane="purple"),
            ("review_required", {"document_id": DOCUMENT_ID}),
        ),
        (event("document.received", document_id=None), ("received", {})),
    ],
)
async def test_event(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    message: EventMessage,
    expected: tuple[str, dict[str, str]],
) -> None:
    """Each kind triggers with the document's id, and the lane when Lekto names a known one."""
    lekto.events.listen.side_effect = streams([message])

    await _set_up(hass, config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN
    event_type, attributes = expected
    assert state.attributes["event_type"] == event_type
    for name in ("document_id", "lane"):
        assert state.attributes.get(name) == attributes.get(name)
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_lane_named_by_the_model(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """The lane arrives as well once pylekto's model names it instead of leaving it an extra."""

    class WithLane(EventMessage):
        lane: str | None = None

    message = event("document.review_required", lane="red")
    lekto.events.listen.side_effect = streams([WithLane.model_validate(message.model_dump())])

    await _set_up(hass, config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["lane"] == "red"
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_other_events(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Events of other kinds leave the entity as it was."""
    lekto.events.listen.side_effect = streams(
        [event("document.node_started", node="ocr", run=1), event("classifier.trained", number=2)]
    )

    await _set_up(hass, config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_event_while_numbers_fail(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """While the numbers cannot be fetched, events still come through."""
    gate = asyncio.Event()

    async def listen(
        *, on_connected: Callable[[], None], **_filters: object
    ) -> AsyncIterator[EventMessage]:
        on_connected()
        await gate.wait()
        yield event("document.review_required", lane="yellow")
        await asyncio.Event().wait()

    lekto.events.listen.side_effect = listen
    await _set_up(hass, config_entry)
    lekto.inbox.summary.side_effect = LektoConnectionError("refused")
    await config_entry.runtime_data.async_refresh()
    numbers = hass.states.get("sensor.lekto_inbox_open")
    assert numbers is not None
    assert numbers.state == STATE_UNAVAILABLE

    gate.set()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["event_type"] == "review_required"
    assert state.attributes["lane"] == "yellow"
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_unavailable_without_stream(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """While the stream is lost the entity is unavailable; it is back before the next event."""
    again = asyncio.Event()
    lekto.events.listen.side_effect = streams(
        LektoConnectionError("refused"),
        [event("document.received"), LektoConnectionError("broken off")],
        [],
    )

    async def wait(_seconds: float) -> None:
        await again.wait()
        again.clear()

    with patch("custom_components.lekto.stream.sleep", wait):
        await _set_up(hass, config_entry)
        never_connected = hass.states.get(ENTITY_ID)
        again.set()
        await hass.async_block_till_done()
        lost = hass.states.get(ENTITY_ID)
        again.set()
        await hass.async_block_till_done()
        back = hass.states.get(ENTITY_ID)

    assert never_connected is not None
    assert never_connected.state == STATE_UNAVAILABLE
    assert lost is not None
    assert lost.state == STATE_UNAVAILABLE
    assert back is not None
    assert back.state not in {STATE_UNAVAILABLE, STATE_UNKNOWN}
    assert back.attributes["event_type"] == "received"
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_restored(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """After a restart the last event is still there."""
    lekto.events.listen.side_effect = streams([])
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(ENTITY_ID, "2026-11-19T08:20:00.000+00:00"),
                {
                    "last_event_type": "review_required",
                    "last_event_attributes": {"document_id": DOCUMENT_ID, "lane": "red"},
                },
            )
        ],
    )

    await _set_up(hass, config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "2026-11-19T08:20:00.000+00:00"
    assert state.attributes["event_type"] == "review_required"
    assert state.attributes["lane"] == "red"
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def _set_up_with_fields(
    hass: HomeAssistant, config_entry: MockConfigEntry, fields: list[str]
) -> None:
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={CONF_EVENT_FIELDS: fields})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_fields(hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry) -> None:
    """Picked fields come from the document and Lekto's names; unknown tags are left out."""
    lekto.events.listen.side_effect = streams([event("document.received")])

    await _set_up_with_fields(hass, config_entry, list(EVENT_FIELDS))

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert {name: state.attributes.get(name) for name in EVENT_FIELDS} == {
        "title": "Electricity bill November",
        "document_date": "2026-11-03",
        "contact": "Example Energy",
        "document_type": "Invoice",
        "tags": ["Car"],
        "space": "Household",
    }
    assert state.attributes["document_id"] == DOCUMENT_ID
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_no_fields_no_request(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Without picked fields the document is not fetched."""
    lekto.events.listen.side_effect = streams([event("document.received")])

    await _set_up_with_fields(hass, config_entry, [])

    lekto.documents.get.assert_not_called()
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_fields_unavailable(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A document Lekto cannot give, or a name it cannot give, leaves the fields out."""
    lekto.events.listen.side_effect = streams([event("document.received"), event("document.filed")])
    lekto.documents.get.side_effect = [
        LektoConnectionError("refused"),
        document(document_date=None, contact_id=None),
    ]
    lekto.document_types.list.side_effect = LektoConnectionError("refused")

    await _set_up_with_fields(hass, config_entry, list(EVENT_FIELDS))

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["event_type"] == "filed"
    assert {name for name in EVENT_FIELDS if name in state.attributes} == {
        "title",
        "tags",
        "space",
    }
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_fields_without_names(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Without the rights to list names, the named fields are left out."""
    rights = [r for r in me().rights if r not in {"master_data:read", "spaces:read"}]
    lekto.connect.return_value = me(rights=rights)
    lekto.events.listen.side_effect = streams([event("document.received")])

    await _set_up_with_fields(hass, config_entry, list(EVENT_FIELDS))

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert {name for name in EVENT_FIELDS if name in state.attributes} == {
        "title",
        "document_date",
    }
    assert await hass.config_entries.async_unload(config_entry.entry_id)


def test_fields_not_recorded() -> None:
    """Titles and names stay out of the recorder's history."""
    assert LektoDocumentEvent._unrecorded_attributes >= set(EVENT_FIELDS)


async def test_fields_keep_order(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """An event whose document comes slowly still goes before the next one."""
    first_done = asyncio.Event()
    fired: list[str] = []

    async def get(_document_id: object) -> object:
        if not first_done.is_set():
            first_done.set()
            await asyncio.sleep(0)
            return document(title="First")
        return document(title="Second")

    lekto.documents.get.side_effect = get
    lekto.events.listen.side_effect = streams([event("document.received"), event("document.filed")])

    @callback
    def changed(change: Event[EventStateChangedData]) -> None:
        state = change.data["new_state"]
        if state is not None and "title" in state.attributes:
            fired.append(state.attributes["title"])

    async_track_state_change_event(hass, ENTITY_ID, changed)

    await _set_up_with_fields(hass, config_entry, ["title"])

    assert fired == ["First", "Second"]
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_fields_name_unavailable() -> None:
    """A name Lekto cannot give at the moment is left out."""
    coordinator = MagicMock()
    coordinator.client.documents.get = AsyncMock(return_value=document())
    coordinator.names.may.return_value = True
    coordinator.names.name = AsyncMock(side_effect=LektoConnectionError("refused"))

    fields = await document_fields(coordinator, UUID(DOCUMENT_ID), ["contact", "tags"])

    assert fields == {"tags": []}
