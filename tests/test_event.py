"""The document event: what happened last to one of the household's documents."""

import asyncio
from typing import TYPE_CHECKING

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State
from pylekto import LektoConnectionError
from pytest_homeassistant.common import mock_restore_cache_with_extra_data

from .const import DOCUMENT_ID, event, streams

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pylekto.models import EventMessage
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

    async def listen(**_filters: object) -> AsyncIterator[EventMessage]:
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
