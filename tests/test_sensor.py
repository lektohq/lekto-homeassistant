"""The sensors: the household's documents in numbers."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pylekto import (
    LektoAuthenticationError,
    LektoConnectionError,
    LektoRateLimitError,
    LektoServerError,
)
from pylekto.models import Problem
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.lekto.const import DOMAIN

from .const import INSTANCE_ID, URL, health, inbox_summary, jobs_summary

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
    "sensor.lekto_health": "ok",
    "sensor.lekto_jobs_failed": "3",
    "sensor.lekto_jobs_waiting": "7",
    "sensor.lekto_search_index_waiting": "6",
}
DISABLED = {
    "sensor.lekto_worker_last_started": "2026-11-19T08:15:00+00:00",
    "sensor.lekto_confirmations_since_training": "9",
}
DIAGNOSTIC = [
    "sensor.lekto_health",
    "sensor.lekto_jobs_failed",
    "sensor.lekto_jobs_waiting",
    "sensor.lekto_search_index_waiting",
    *DISABLED,
]


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
    assert device.manufacturer == "LektoHQ"
    assert device.model == "0.9"
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.sw_version == "0.17.3"
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
async def test_update_rate_limited(
    hass: HomeAssistant, lekto: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Told by Lekto when to ask again, the next fetch of the numbers waits that long."""
    lekto.inbox.summary.side_effect = LektoRateLimitError(
        Problem(title="Too Many Requests", status=429), 300.0
    )
    await _next_update(hass, freezer)
    asked = lekto.inbox.summary.await_count

    await _next_update(hass, freezer)

    assert lekto.inbox.summary.await_count == asked
    freezer.tick(timedelta(seconds=240))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert lekto.inbox.summary.await_count == asked + 1


@pytest.mark.usefixtures("loaded_entry")
@pytest.mark.parametrize("failing", ["inbox", "documents", "jobs"])
async def test_update_failed(
    hass: HomeAssistant,
    lekto: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    failing: str,
) -> None:
    """The sensors turn unavailable while Lekto does not answer, logged once, and come back."""
    request = {
        "inbox": lekto.inbox.summary,
        "documents": lekto.documents.count,
        "jobs": lekto.jobs.summary,
    }[failing]

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


@pytest.mark.usefixtures("loaded_entry")
@pytest.mark.parametrize("failing", ["inbox", "jobs", "classifier"])
async def test_update_starts_reauth(
    hass: HomeAssistant, lekto: MagicMock, freezer: FrozenDateTimeFactory, failing: str
) -> None:
    """A token Lekto stops accepting asks for a new one."""
    {
        "inbox": lekto.inbox.summary,
        "jobs": lekto.jobs.summary,
        "classifier": lekto.classifier.status,
    }[failing].side_effect = LektoAuthenticationError(Problem(title="Unauthorized", status=401))

    await _next_update(hass, freezer)

    state = hass.states.get("sensor.lekto_inbox_open")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


@pytest.mark.usefixtures("lekto")
async def test_diagnostic_sensors(
    hass: HomeAssistant, config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Lekto's state is diagnostic; the rarely needed sensors start disabled."""
    await _set_up(hass, config_entry)

    for entity_id in DIAGNOSTIC:
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.entity_category is EntityCategory.DIAGNOSTIC
    for entity_id in set(SENSORS) - set(DIAGNOSTIC):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.entity_category is None
    for entity_id in DISABLED:
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "lekto")
async def test_disabled_sensors(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Enabled, the worker's last start and the confirmations since training show their values."""
    await _set_up(hass, config_entry)

    for entity_id, value in DISABLED.items():
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state == value


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unknown_states(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A health a newer Lekto knows, or no worker start yet, leaves the sensor unknown."""
    lekto.health.get.return_value = health(status="resting")
    lekto.jobs.summary.return_value = jobs_summary(last_started_at=None)

    await _set_up(hass, config_entry)

    for entity_id in ("sensor.lekto_health", "sensor.lekto_worker_last_started"):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_without_search_and_classifier(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A Lekto without search index or classifier sets up; only their sensors are unavailable."""
    lekto.search.status.side_effect = LektoServerError(Problem(title="Unavailable", status=503))
    lekto.classifier.status.side_effect = LektoServerError(Problem(title="Unavailable", status=503))

    await _set_up(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    for entity_id in (
        "sensor.lekto_search_index_waiting",
        "sensor.lekto_confirmations_since_training",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
    for entity_id in (
        "sensor.lekto_inbox_open",
        "sensor.lekto_health",
        "sensor.lekto_jobs_waiting",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(("status", "value"), [("degraded", "degraded"), ("unavailable", "down")])
async def test_health(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    status: str,
    value: str,
) -> None:
    """Lekto's own unavailable reads as down, apart from Home Assistant's unavailable."""
    lekto.health.get.return_value = health(status=status)

    await _set_up(hass, config_entry)

    state = hass.states.get("sensor.lekto_health")
    assert state is not None
    assert state.state == value


async def test_no_jobs(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Without any job the job counts are zero."""
    lekto.jobs.summary.return_value = jobs_summary(kinds=[])

    await _set_up(hass, config_entry)

    for entity_id in ("sensor.lekto_jobs_failed", "sensor.lekto_jobs_waiting"):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "0"
