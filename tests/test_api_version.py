"""The repair that tells when Lekto speaks another version of its API."""

from typing import TYPE_CHECKING

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pylekto import API_VERSION
from pytest_homeassistant.common import MockConfigEntry

from custom_components.lekto.const import DOMAIN

from .const import me

if TYPE_CHECKING:
    from unittest.mock import MagicMock


async def _set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _api(lekto: MagicMock, api_version: str) -> None:
    lekto.connect.return_value = me(api_version=api_version)
    lekto.auth.me.return_value = me(api_version=api_version)


@pytest.mark.parametrize(
    ("api_version", "key"),
    [("0.9", "api_newer"), ("0.1", "api_older"), ("0.2.1", "api_unknown")],
)
async def test_repair(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    api_version: str,
    key: str,
) -> None:
    """Another API raises a repair that says which side to update; the integration goes on."""
    _api(lekto, api_version)

    await _set_up(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"{config_entry.entry_id}_api_version")
    assert issue is not None
    assert issue.translation_key == key
    assert not issue.is_fixable
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.config_entry_id == config_entry.entry_id
    assert issue.translation_placeholders == {
        "name": "Lekto",
        "lekto_version": "0.16.0",
        "api_version": api_version,
        "integration_api": API_VERSION,
    }


async def test_fits(hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry) -> None:
    """The API this integration speaks raises no repair."""
    _api(lekto, API_VERSION)

    await _set_up(hass, config_entry)

    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"{config_entry.entry_id}_api_version") is None
    )


async def test_gone_once_it_fits(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Set up again with an API that fits, the repair goes; a lost right's repair stays."""
    _api(lekto, "0.9")
    await _set_up(hass, config_entry)
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, f"{config_entry.entry_id}_api_version") is not None
    rights = [r for r in me().rights if r != "system:read"]
    lekto.connect.return_value = me(rights=rights)
    lekto.auth.me.return_value = me(rights=rights)

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert issues.async_get_issue(DOMAIN, f"{config_entry.entry_id}_api_version") is None
    assert issues.async_get_issue(DOMAIN, f"{config_entry.entry_id}_diagnostics_lost") is not None
