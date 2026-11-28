"""Setting up and unloading the integration."""

from typing import TYPE_CHECKING

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.loader import async_get_integration
from pylekto import (
    LektoAuthenticationError,
    LektoConnectionError,
    LektoForbiddenError,
    LektoResponseError,
)
from pylekto.models import Problem

from custom_components.lekto.const import DOMAIN

from . import setup_integration
from .const import NEW_URL, TOKEN, me

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pylekto.models import Me
    from pytest_homeassistant.common import MockConfigEntry


async def test_integration(hass: HomeAssistant) -> None:
    """The manifest names the integration as a custom one of this repository."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.name == "Lekto"
    assert not integration.is_built_in
    assert integration.pkg_path == "custom_components.lekto"


async def test_setup_and_unload(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """The entry connects, keeps the client in its coordinator and unloads again."""
    assert await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.client is lekto

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    unloaded = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert unloaded is not None
    assert unloaded.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            LektoAuthenticationError(Problem(title="Unauthorized", status=401)),
            (ConfigEntryState.SETUP_ERROR, "invalid_auth", None),
        ),
        (
            LektoForbiddenError(Problem(title="Forbidden", status=403)),
            (
                ConfigEntryState.SETUP_ERROR,
                "missing_rights",
                {"rights": "admin:count_all, documents:count"},
            ),
        ),
        (
            LektoResponseError("no instance_id"),
            (ConfigEntryState.SETUP_ERROR, "unsupported", None),
        ),
        (
            LektoConnectionError("refused"),
            (ConfigEntryState.SETUP_RETRY, "cannot_connect", None),
        ),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    error: Exception,
    expected: tuple[ConfigEntryState, str, dict[str, str] | None],
) -> None:
    """A revoked token or a server that is no Lekto fails the setup; an unreachable one retries."""
    lekto.connect.side_effect = error

    await setup_integration(hass, config_entry)

    assert (
        config_entry.state,
        config_entry.error_reason_translation_key,
        config_entry.error_reason_translation_placeholders,
    ) == expected


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (me(instance_id="0195f3c2-7a10-7c4e-9b1d-2f6a8e4c1dff"), ("wrong_instance", None)),
        (
            me(rights=["documents:count"]),
            ("missing_rights", {"rights": "admin:count_all"}),
        ),
    ],
)
async def test_setup_no_longer_fits(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    answer: Me,
    expected: tuple[str, dict[str, str] | None],
) -> None:
    """Another instance behind the address, or a token without the rights, fails the setup."""
    lekto.connect.return_value = answer

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        config_entry.error_reason_translation_key,
        config_entry.error_reason_translation_placeholders,
    ) == expected


@pytest.mark.parametrize(
    ("error", "answer"),
    [
        (LektoAuthenticationError(Problem(title="Unauthorized", status=401)), None),
        (LektoForbiddenError(Problem(title="Forbidden", status=403)), None),
        (None, me(rights=["documents:read"])),
    ],
)
async def test_setup_starts_reauth(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    error: Exception | None,
    answer: Me | None,
) -> None:
    """A refused token, or one without the rights, asks for a new token."""
    lekto.connect.side_effect = error
    if answer is not None:
        lekto.connect.return_value = answer

    await setup_integration(hass, config_entry)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_reconfigure_repairs_wrong_instance(
    hass: HomeAssistant, lekto_class: MagicMock, config_entry: MockConfigEntry
) -> None:
    """An entry whose address leads to another instance sets up after reconfiguring it."""
    lekto = lekto_class.return_value
    lekto.connect.return_value = me(instance_id="0195f3c2-7a10-7c4e-9b1d-2f6a8e4c1dff")
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    lekto.connect.return_value = me()
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: NEW_URL, CONF_VERIFY_SSL: True}
    )
    await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    reloaded = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert reloaded is not None
    assert reloaded.state is ConfigEntryState.LOADED
    assert lekto_class.call_args.args == (NEW_URL, TOKEN)
