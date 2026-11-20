"""The diagnostics: what helps with a problem, without anything personal."""

import json
from typing import TYPE_CHECKING

import pytest
from homeassistant.components.diagnostics import REDACTED
from pylekto import LektoServerError
from pylekto.models import Problem
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry

from .const import INSTANCE_ID, TOKEN, URL, me

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry
    from pytest_homeassistant.typing import ClientSessionGenerator


@pytest.mark.usefixtures("lekto")
async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, config_entry: MockConfigEntry
) -> None:
    """The file holds versions, rights and the numbers, but no token, address or name."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    entry = diagnostics["entry"]
    assert isinstance(entry, dict)
    assert entry["data"] == {
        "api_token": REDACTED,
        "url": REDACTED,
        "verify_ssl": True,
        "capabilities": ["diagnostics", "events", "names", "spaces"],
    }
    assert entry["unique_id"] == REDACTED
    assert entry["title"] == REDACTED
    text = json.dumps(diagnostics)
    for secret in (TOKEN, URL, INSTANCE_ID, "homeassistant", "Home Assistant"):
        assert secret not in text, secret
    assert diagnostics["lekto"] == {
        "lekto_version": "0.16.0",
        "api_version": "0.2",
        "capabilities": ["diagnostics", "events", "names", "spaces"],
        "rights": [
            "admin:count_all",
            "admin:documents_all",
            "admin:mailboxes",
            "admin:private_webhooks",
            "documents:count",
            "documents:read",
            "documents:upload",
            "master_data:read",
            "spaces:read",
            "system:read",
            "system:write",
            "webhooks:read",
            "webhooks:write",
        ],
    }
    data = diagnostics["data"]
    assert isinstance(data, dict)
    assert data["documents"] == 1234
    inbox = data["inbox"]
    assert isinstance(inbox, dict)
    assert inbox["worst_lane"] == "red"


async def test_diagnostics_without_search(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Without a search index or classifier the file says so."""
    missing = LektoServerError(Problem(title="Unavailable", status=503))
    lekto.search.status.side_effect = missing
    lekto.classifier.status.side_effect = missing
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    data = diagnostics["data"]
    assert isinstance(data, dict)
    assert data["search"] is None
    assert data["classifier"] is None


async def test_diagnostics_not_loaded(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """An entry that failed to set up gives only its redacted self."""
    lekto.connect.return_value = me(instance_id="0195f3c2-7a10-7c4e-9b1d-2f6a8e4c1dff")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert list(diagnostics) == ["entry"]
    assert TOKEN not in json.dumps(diagnostics)
