"""The Lekto integration: Lekto DMS in Home Assistant."""

from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from pylekto import (
    LektoAuthenticationError,
    LektoClient,
    LektoError,
    LektoForbiddenError,
    LektoResponseError,
)

from .capabilities import Capability, capabilities, missing_rights
from .const import DOMAIN, REQUIRED_RIGHTS
from .coordinator import LektoConfigEntry, LektoCoordinator
from .repairs import note_issues
from .services import async_setup_services
from .stream import listen

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.SENSOR, Platform.UPDATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Register the actions, so they exist even while no entry is loaded."""
    async_setup_services(hass)
    return True


def create_client(hass: HomeAssistant, data: Mapping[str, Any]) -> LektoClient:
    """Return a client of the instance in ``data`` on Home Assistant's shared httpx2 client."""
    return LektoClient(
        data[CONF_URL],
        data[CONF_API_TOKEN],
        client=get_async_client(hass, verify_ssl=data[CONF_VERIFY_SSL]),
    )


async def async_setup_entry(hass: HomeAssistant, entry: LektoConfigEntry) -> None:
    """Connect to Lekto and check that the token still fits the entry."""
    client = create_client(hass, entry.data)
    try:
        me = await client.connect()
    except LektoAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    # An upload token may not even ask who it is.
    except LektoForbiddenError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="missing_rights",
            translation_placeholders={"rights": ", ".join(sorted(REQUIRED_RIGHTS))},
        ) from err
    except LektoResponseError as err:
        raise ConfigEntryError(translation_domain=DOMAIN, translation_key="unsupported") from err
    except LektoError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    if str(me.instance_id) != entry.unique_id:
        raise ConfigEntryError(translation_domain=DOMAIN, translation_key="wrong_instance")
    if missing := missing_rights(me.rights):
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="missing_rights",
            translation_placeholders={"rights": ", ".join(missing)},
        )
    given = capabilities(me.rights)
    note_issues(hass, entry, me, given)
    coordinator = LektoCoordinator(hass, entry, client, me, given)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_create_background_task(hass, coordinator.names.load(), f"{DOMAIN} names")
    if Capability.EVENTS in given:
        entry.async_create_background_task(hass, listen(hass, entry), f"{DOMAIN} event stream")


async def async_unload_entry(hass: HomeAssistant, entry: LektoConfigEntry) -> None:
    """Unload the entry's platforms; the httpx2 client is Home Assistant's and stays open."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
