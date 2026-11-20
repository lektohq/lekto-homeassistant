"""The options: what the document event carries beside the document's id."""

from typing import TYPE_CHECKING

import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.lekto.const import CONF_CAPABILITIES, CONF_EVENT_FIELDS, DOMAIN

from .const import ENTRY_DATA, INSTANCE_ID, me

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("rights", "offered"),
    [
        (None, ["title", "document_date", "contact", "document_type", "tags", "space"]),
        (
            ["admin:count_all", "documents:count", "documents:read", "admin:documents_all"],
            ["title", "document_date"],
        ),
    ],
)
async def test_options(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    rights: list[str] | None,
    offered: list[str],
) -> None:
    """The options offer the fields the token's rights allow, and keep the pick."""
    if rights is not None:
        lekto.connect.return_value = me(rights=rights)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"] is not None
    selector = result["data_schema"].schema[CONF_EVENT_FIELDS]
    assert selector.config["options"] == offered

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_EVENT_FIELDS: ["title"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_EVENT_FIELDS: ["title"]}


async def test_options_without_events(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Without the rights of the document event there is nothing to pick."""
    lekto.connect.return_value = me(rights=["admin:count_all", "documents:count"])
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_events"


async def test_options_drop_fields_no_longer_offered(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A field picked under a token with more rights is not suggested again."""
    rights = [r for r in me().rights if r != "master_data:read"]
    lekto.connect.return_value = me(rights=rights)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_EVENT_FIELDS: ["title", "contact"]}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["data_schema"] is not None
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description
    }
    assert suggested == {CONF_EVENT_FIELDS: ["title"]}


@pytest.mark.parametrize(
    ("capabilities", "offered"),
    [
        (["events", "names", "spaces"], 6),
        (["events"], 2),
    ],
)
async def test_options_not_loaded(
    hass: HomeAssistant, capabilities: list[str], offered: int
) -> None:
    """An entry that is not set up offers what its last capabilities allowed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Lekto",
        unique_id=INSTANCE_ID,
        data=ENTRY_DATA | {CONF_CAPABILITIES: capabilities},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["data_schema"] is not None
    selector = result["data_schema"].schema[CONF_EVENT_FIELDS]
    assert len(selector.config["options"]) == offered
