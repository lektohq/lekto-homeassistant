"""The sensors: the household's documents in numbers."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pylekto import LektoConnectionError
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.lekto.const import DOMAIN

from .const import INSTANCE_ID, URL, inbox_summary

if TYPE_CHECKING:
    from unittest.mock import MagicMock

SENSORS = {
    "sensor.lekto_inbox_open": "11",
    "sensor.lekto_inbox_new": "3",
    "sensor.lekto_inbox_review": "5",
    "sensor.lekto_inbox_action_needed": "2",
    "sensor.lekto_inbox_processing": "1",
    "sensor.lekto_inbox_worst_lane": "red",
    "sensor.lekto_documents": "1234",
}


async def _set_up(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _next_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    # The coordinator adds a fraction of a second to 60 seconds and refreshes in the background.
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("lekto")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Each number of every user's documents is a sensor of the instance's device."""
    await _set_up(hass, config_entry)

    for entity_id, value in SENSORS.items():
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state == value
    entry = entity_registry.async_get("sensor.lekto_inbox_open")
    assert entry is not None
    assert entry.unique_id == f"{INSTANCE_ID}_inbox_open"

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, INSTANCE_ID), config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Lekto"
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.sw_version == "0.16.0"
    assert device.configuration_url == URL


async def test_household_numbers(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """The numbers count every user's documents."""
    await _set_up(hass, config_entry)

    lekto.inbox.summary.assert_called_with(all_users=True)
    lekto.documents.count.assert_called_with(all_users=True)


@pytest.mark.parametrize("lane", [None, "purple"])
async def test_worst_lane_unknown(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry, lane: str | None
) -> None:
    """Only documents in processing, or a lane a newer Lekto knows, leave the worst lane unknown."""
    lekto.inbox.summary.return_value = inbox_summary(worst_lane=lane)

    await _set_up(hass, config_entry)

    state = hass.states.get("sensor.lekto_inbox_worst_lane")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Return the config entry, set up with the client of ``lekto``."""
    await _set_up(hass, config_entry)
    assert config_entry.runtime_data.client is lekto
    return config_entry


@pytest.mark.usefixtures("loaded_entry")
@pytest.mark.parametrize("failing", ["inbox", "documents"])
async def test_update_failed(
    hass: HomeAssistant,
    lekto: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    failing: str,
) -> None:
    """The sensors turn unavailable while Lekto does not answer, logged once, and come back."""
    request = lekto.inbox.summary if failing == "inbox" else lekto.documents.count

    request.side_effect = LektoConnectionError("refused")
    await _next_update(hass, freezer)
    await _next_update(hass, freezer)

    state = hass.states.get("sensor.lekto_inbox_open")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert caplog.text.count("Error fetching lekto data") == 1

    request.side_effect = None
    await _next_update(hass, freezer)

    state = hass.states.get("sensor.lekto_inbox_open")
    assert state is not None
    assert state.state == "11"
    assert "Fetching lekto data recovered" in caplog.text


async def test_first_refresh_failed(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Without the first numbers the setup is tried again later."""
    lekto.inbox.summary.side_effect = LektoConnectionError("refused")

    await _set_up(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.error_reason_translation_key == "update_failed"
