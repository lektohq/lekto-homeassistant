"""The base of the Lekto integration's entities."""

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LektoCoordinator


class LektoEntity(CoordinatorEntity[LektoCoordinator]):
    """An entity of the Lekto instance's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LektoCoordinator, key: str) -> None:
        """Name the entity by its key, under the instance's id."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.instance_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.instance_id)},
            name="Lekto",
            entry_type=DeviceEntryType.SERVICE,
            sw_version=coordinator.lekto_version,
            configuration_url=coordinator.config_entry.data[CONF_URL],
        )
