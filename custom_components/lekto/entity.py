"""The base of the Lekto integration's entities."""

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LektoCoordinator


class LektoEntity(Entity):
    """An entity of the Lekto instance's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LektoCoordinator, key: str) -> None:
        """Name the entity by its key, under the instance's id."""
        self._attr_unique_id = f"{coordinator.instance_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.instance_id)},
            name="Lekto",
            entry_type=DeviceEntryType.SERVICE,
            sw_version=coordinator.lekto_version,
            configuration_url=coordinator.config_entry.data[CONF_URL],
        )


class LektoCoordinatorEntity(CoordinatorEntity[LektoCoordinator], LektoEntity):
    """An entity that shows the coordinator's numbers and is unavailable while they fail."""

    def __init__(self, coordinator: LektoCoordinator, key: str) -> None:
        """Follow the coordinator; neither base calls the other's constructor."""
        CoordinatorEntity.__init__(self, coordinator)
        LektoEntity.__init__(self, coordinator, key)
