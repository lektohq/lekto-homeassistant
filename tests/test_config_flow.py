"""The config flow: address and token, checked against Lekto."""

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResultType
from pylekto import (
    LektoAuthenticationError,
    LektoConnectionError,
    LektoForbiddenError,
    LektoResponseError,
)
from pylekto.models import Problem

from custom_components.lekto.const import DOMAIN

from .const import ENTRY_DATA, INSTANCE_ID, TOKEN, URL, me

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("lekto")
async def test_user(hass: HomeAssistant) -> None:
    """A token with the required rights sets the instance up under its id."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: f" {URL}/ ", CONF_API_TOKEN: TOKEN, CONF_VERIFY_SSL: True},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lekto"
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == INSTANCE_ID


async def test_user_shared_client(hass: HomeAssistant, lekto_class: MagicMock) -> None:
    """The client sends through Home Assistant's httpx2 client, verifying TLS as asked."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    with patch("custom_components.lekto.get_async_client") as get_async_client:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ENTRY_DATA | {CONF_VERIFY_SSL: False}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    get_async_client.assert_called_once_with(hass, verify_ssl=False)
    lekto_class.assert_called_once_with(URL, TOKEN, client=get_async_client.return_value)


@pytest.mark.parametrize(
    "rights", [["admin:count_all", "documents:count"], ["admin:count_all", "documents:read"]]
)
async def test_user_counting_rights(
    hass: HomeAssistant, lekto: MagicMock, rights: list[str]
) -> None:
    """Counting comes with documents:count, or with documents:read that includes it."""
    lekto.connect.return_value = me(rights=rights)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("error", "base"),
    [
        (LektoAuthenticationError(Problem(title="Unauthorized", status=401)), "invalid_auth"),
        (LektoForbiddenError(Problem(title="Forbidden", status=403)), "missing_rights"),
        (LektoResponseError("no instance_id"), "unsupported"),
        (LektoConnectionError("refused"), "cannot_connect"),
        (RuntimeError("surprise"), "unknown"),
    ],
)
async def test_user_error(
    hass: HomeAssistant, lekto: MagicMock, error: Exception, base: str
) -> None:
    """A failed check shows its error; the next try with a fixed cause succeeds."""
    lekto.connect.side_effect = error
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base}

    lekto.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "rights", [["documents:count", "documents:read"], ["admin:count_all", "documents:upload"]]
)
async def test_user_missing_rights(
    hass: HomeAssistant, lekto: MagicMock, rights: list[str]
) -> None:
    """A token that may not count the household is refused."""
    lekto.connect.return_value = me(rights=rights)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_rights"}
    placeholders = result["description_placeholders"]
    assert placeholders is not None
    assert placeholders["rights"] == "admin:count_all, documents:count"


async def test_user_already_configured(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """The same instance is set up only once, whatever the token and its rights."""
    lekto.connect.return_value = me(rights=["documents:upload"])
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA | {CONF_API_TOKEN: "lekto_anotherMadeupToken"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
