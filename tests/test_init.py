"""Home Assistant finds the integration."""

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from custom_components.lekto.const import DOMAIN


async def test_integration(hass: HomeAssistant) -> None:
    """The manifest names the integration as a custom one of this repository."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.name == "Lekto"
    assert not integration.is_built_in
    assert integration.pkg_path == "custom_components.lekto"
