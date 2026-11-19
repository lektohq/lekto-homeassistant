"""The sensors of the Lekto integration: the household's documents in numbers."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from .entity import LektoEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from .coordinator import LektoConfigEntry, LektoCoordinator, LektoData

# The coordinator fetches for every entity at once.
PARALLEL_UPDATES = 0

LANES = ["green", "yellow", "red"]


@dataclass(frozen=True, kw_only=True)
class LektoSensorEntityDescription(SensorEntityDescription):
    """A sensor and how it reads its value from the household's numbers."""

    value: Callable[[LektoData], StateType]


def _worst_lane(data: LektoData) -> str | None:
    """Return the worst lane; one a newer Lekto knows and this integration does not is unknown."""
    lane = data.inbox.worst_lane
    return lane if lane in LANES else None


def _count(key: str, value: Callable[[LektoData], int]) -> LektoSensorEntityDescription:
    return LektoSensorEntityDescription(
        key=key,
        translation_key=key,
        state_class=SensorStateClass.MEASUREMENT,
        value=value,
    )


SENSORS: tuple[LektoSensorEntityDescription, ...] = (
    _count("inbox_open", lambda data: data.inbox.open),
    _count("inbox_new", lambda data: data.inbox.new),
    _count("inbox_review", lambda data: data.inbox.review),
    _count("inbox_intervene", lambda data: data.inbox.intervene),
    _count("inbox_processing", lambda data: data.inbox.processing),
    LektoSensorEntityDescription(
        key="inbox_worst_lane",
        translation_key="inbox_worst_lane",
        device_class=SensorDeviceClass.ENUM,
        options=LANES,
        value=_worst_lane,
    ),
    _count("documents", lambda data: data.documents),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: LektoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors of the instance."""
    async_add_entities(LektoSensor(entry.runtime_data, description) for description in SENSORS)


class LektoSensor(LektoEntity, SensorEntity):
    """A number of the household's documents."""

    entity_description: LektoSensorEntityDescription

    def __init__(
        self, coordinator: LektoCoordinator, description: LektoSensorEntityDescription
    ) -> None:
        """Make the sensor of ``description``."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor's value from the coordinator's latest numbers."""
        return self.entity_description.value(self.coordinator.data)
