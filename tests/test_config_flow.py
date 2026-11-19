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

from .const import ENTRY_DATA, INSTANCE_ID, NEW_TOKEN, NEW_URL, TOKEN, URL, me

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
    "rights",
    [
        ["admin:documents_all", "documents:read", "system:read"],
        ["admin:count_all", "documents:read", "system:read"],
        ["admin:count_all", "admin:documents_all", "documents:count", "system:read"],
        ["admin:count_all", "admin:documents_all", "documents:read"],
    ],
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
    assert (
        placeholders["rights"]
        == "admin:count_all, admin:documents_all, documents:read, system:read"
    )


async def test_user_already_configured(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """The same instance is set up only once, whatever the token and its rights."""
    lekto.connect.return_value = me(rights=["documents:upload"])
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA | {CONF_API_TOKEN: NEW_TOKEN}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant, lekto_class: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A new token of the same instance replaces the old one; nothing else changes."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: NEW_TOKEN}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == ENTRY_DATA | {CONF_API_TOKEN: NEW_TOKEN}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert lekto_class.call_args.args == (URL, NEW_TOKEN)


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
async def test_reauth_error(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    error: Exception,
    base: str,
) -> None:
    """A failed check shows its error; the next try with a fixed cause saves the token."""
    config_entry.add_to_hass(hass)
    lekto.connect.side_effect = error
    result = await config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: NEW_TOKEN}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base}

    lekto.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: NEW_TOKEN}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_missing_rights(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A new token without the rights is refused, and the old one stays."""
    config_entry.add_to_hass(hass)
    lekto.connect.return_value = me(rights=["documents:read"])
    result = await config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: NEW_TOKEN}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_rights"}
    assert config_entry.data == ENTRY_DATA


async def test_reauth_other_instance(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A token of another instance is refused, and the old one stays."""
    config_entry.add_to_hass(hass)
    lekto.connect.return_value = me(instance_id="0195f3c2-7a10-7c4e-9b1d-2f6a8e4c1dff")
    result = await config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: NEW_TOKEN}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert config_entry.data == ENTRY_DATA


async def test_reconfigure(
    hass: HomeAssistant, lekto_class: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A new address of the same instance replaces the old one; the token stays."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    placeholders = result["description_placeholders"]
    assert placeholders is not None
    assert placeholders["name"] == "Lekto"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: f"{NEW_URL}/", CONF_VERIFY_SSL: False}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == ENTRY_DATA | {CONF_URL: NEW_URL, CONF_VERIFY_SSL: False}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert lekto_class.call_args.args == (NEW_URL, TOKEN)


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
async def test_reconfigure_error(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    error: Exception,
    base: str,
) -> None:
    """A failed check shows its error; the next try with a fixed cause saves the address."""
    config_entry.add_to_hass(hass)
    lekto.connect.side_effect = error
    result = await config_entry.start_reconfigure_flow(hass)
    new = {CONF_URL: NEW_URL, CONF_VERIFY_SSL: True}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], new)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base}

    lekto.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], new)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_missing_rights(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Behind the new address the token lacks rights: the old address stays."""
    config_entry.add_to_hass(hass)
    lekto.connect.return_value = me(rights=["documents:read"])
    result = await config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: NEW_URL, CONF_VERIFY_SSL: True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_rights"}
    assert config_entry.data == ENTRY_DATA


async def test_reconfigure_other_instance(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """An address of another instance is refused, and the old one stays."""
    config_entry.add_to_hass(hass)
    lekto.connect.return_value = me(instance_id="0195f3c2-7a10-7c4e-9b1d-2f6a8e4c1dff")
    result = await config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: NEW_URL, CONF_VERIFY_SSL: True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert config_entry.data == ENTRY_DATA
