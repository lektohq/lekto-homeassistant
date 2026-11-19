"""The Lekto integration: Lekto DMS in Home Assistant."""

from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.httpx_client import get_async_client
from pylekto import (
    LektoAuthenticationError,
    LektoClient,
    LektoError,
    LektoForbiddenError,
    LektoResponseError,
)

from .const import DOMAIN, REQUIRED_RIGHTS
from .coordinator import LektoConfigEntry, LektoCoordinator

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]


def create_client(hass: HomeAssistant, data: Mapping[str, Any]) -> LektoClient:
    """Return a client of the instance in ``data`` on Home Assistant's shared httpx2 client."""
    return LektoClient(
        data[CONF_URL],
        data[CONF_API_TOKEN],
        client=get_async_client(hass, verify_ssl=data[CONF_VERIFY_SSL]),
    )


def missing_rights(rights: Iterable[str]) -> list[str]:
    """Return the rights Home Assistant needs that ``rights`` lack, sorted."""
    given = set(rights)
    return sorted(right for right, holders in REQUIRED_RIGHTS.items() if given.isdisjoint(holders))


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
    coordinator = LektoCoordinator(hass, entry, client, me)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: LektoConfigEntry) -> None:
    """Unload the entry's platforms; the httpx2 client is Home Assistant's and stays open."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
