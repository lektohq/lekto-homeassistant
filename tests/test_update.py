"""The update entity: Lekto's version and the newest release."""

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.update import ATTR_INSTALLED_VERSION, ATTR_LATEST_VERSION
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from . import setup_integration
from .const import INSTANCE_ID, me, version

if TYPE_CHECKING:
    from unittest.mock import MagicMock

UPDATE = "update.lekto"


async def _next_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    # The coordinator adds a fraction of a second to 60 seconds and refreshes in the background.
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("lekto")
async def test_update_available(
    hass: HomeAssistant, config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """A newer release shows as an update with its page; Lekto is updated where it runs."""
    await setup_integration(hass, config_entry)

    state = hass.states.get(UPDATE)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.17.3"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.18.0"
    assert state.attributes["release_url"] == "https://releases.example.com/lekto/v0.18.0"
    assert state.attributes["supported_features"] == 0
    entry = entity_registry.async_get(UPDATE)
    assert entry is not None
    assert entry.unique_id == f"{INSTANCE_ID}_update"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_up_to_date(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Without a newer release, the newest is the installed one."""
    lekto.version.get.return_value = version(latest=None, update_available=False)

    await setup_integration(hass, config_entry)

    state = hass.states.get(UPDATE)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_LATEST_VERSION] == "0.17.3"
    assert state.attributes["release_url"] is None


async def test_updated_before_next_look(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Updated in place, Lekto still names the release it found; it is installed, so no link."""
    lekto.version.get.return_value = version(update_available=False)

    await setup_integration(hass, config_entry)

    state = hass.states.get(UPDATE)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["release_url"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"update_check": False, "checked_at": None, "latest": None, "update_available": False},
        {"checked_at": None, "latest": None, "update_available": False},
    ],
    ids=["check_off", "not_checked_yet"],
)
async def test_newest_unknown(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    changes: dict[str, object],
) -> None:
    """While Lekto does not look for releases, or has not yet, the newest is unknown."""
    lekto.version.get.return_value = version(**changes)

    await setup_integration(hass, config_entry)

    state = hass.states.get(UPDATE)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.17.3"
    assert state.attributes[ATTR_LATEST_VERSION] is None


async def test_without_right(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Without ``system:read`` there is no update entity, and nothing asks for the version."""
    rights = [r for r in me().rights if r != "system:read"]
    lekto.connect.return_value = me(rights=rights)
    lekto.auth.me.return_value = me(rights=rights)

    await setup_integration(hass, config_entry)

    assert hass.states.get(UPDATE) is None
    lekto.version.get.assert_not_called()


async def test_lekto_updated(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """When Lekto runs another version than at setup, the entry is set up again."""
    await setup_integration(hass, config_entry)
    lekto.version.get.return_value = version(
        lekto_version="0.18.0", latest=None, update_available=False
    )

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await _next_update(hass, freezer)
        await _next_update(hass, freezer)

    reload.assert_called_once_with(config_entry.entry_id)


async def test_other_version_than_at_setup(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A version other than the one Lekto named at setup, and that stays, reloads nothing."""
    lekto.version.get.return_value = version(lekto_version="0.18.0")

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await setup_integration(hass, config_entry)
        await _next_update(hass, freezer)

    reload.assert_not_called()


@pytest.mark.usefixtures("lekto")
async def test_lekto_same_version(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The same version keeps the entry as it is."""
    await setup_integration(hass, config_entry)

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await _next_update(hass, freezer)

    reload.assert_not_called()
