"""The update entity of the Lekto integration: whether a newer Lekto is out."""

from typing import TYPE_CHECKING, override

from homeassistant.components.update import UpdateEntity
from homeassistant.const import EntityCategory

from .capabilities import Capability
from .entity import LektoCoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import LektoConfigEntry, LektoCoordinator


# The coordinator fetches the versions with the numbers.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: LektoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the update entity, if the token may read Lekto's versions."""
    coordinator = entry.runtime_data
    if Capability.DIAGNOSTICS in coordinator.capabilities:
        async_add_entities([LektoUpdate(coordinator)])


class LektoUpdate(LektoCoordinatorEntity, UpdateEntity):
    """Lekto's version and the newest release; Lekto is updated where it runs, not from here."""

    # The device's main feature carries the device's name: update.lekto, not update.lekto_lekto.
    _attr_name = None
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: LektoCoordinator) -> None:
        """Make the update entity of the instance."""
        super().__init__(coordinator, "update")

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the version Lekto runs."""
        version = self.coordinator.data.version
        return version.lekto_version if version else self.coordinator.lekto_version

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the newest release; unknown while Lekto does not look for releases."""
        version = self.coordinator.data.version
        if version is None or not version.update_check or version.checked_at is None:
            return None
        if version.update_available and version.latest is not None:
            return version.latest.version
        return version.lekto_version

    @property
    @override
    def release_url(self) -> str | None:
        """Return the page of the newest release, while it is not the one installed."""
        version = self.coordinator.data.version
        if version is None or not version.update_available or version.latest is None:
            return None
        return version.latest.url
