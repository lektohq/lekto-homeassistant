"""Tests of the Lekto integration."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> bool:
    """Set the entry up, adding it to Home Assistant first if it is new; say whether it loaded."""
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    loaded = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return loaded
