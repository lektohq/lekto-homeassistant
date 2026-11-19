"""The sensors of the Lekto integration: the household's documents in numbers, and Lekto's state."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory

from .entity import LektoEntity

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from .coordinator import LektoConfigEntry, LektoCoordinator, LektoData

# The coordinator fetches for every entity at once.
PARALLEL_UPDATES = 0

LANES = ["green", "yellow", "red"]
# Lekto's "unavailable" is Home Assistant's name for an entity without a state.
HEALTH = {"ok": "ok", "degraded": "degraded", "unavailable": "down"}


@dataclass(frozen=True, kw_only=True)
class LektoSensorEntityDescription(SensorEntityDescription):
    """A sensor and how it reads its value from the coordinator's data."""

    value: Callable[[LektoData], StateType | datetime]
    available: Callable[[LektoData], bool] = lambda _: True


def _worst_lane(data: LektoData) -> str | None:
    """Return the worst lane; one a newer Lekto knows and this integration does not is unknown."""
    lane = data.inbox.worst_lane
    return lane if lane in LANES else None


def _health(data: LektoData) -> str | None:
    """Return Lekto's state; one a newer Lekto knows and this integration does not is unknown."""
    return HEALTH.get(data.health.status)


def _count(
    key: str, value: Callable[[LektoData], int], *, diagnostic: bool = False
) -> LektoSensorEntityDescription:
    return LektoSensorEntityDescription(
        key=key,
        translation_key=key,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC if diagnostic else None,
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
    LektoSensorEntityDescription(
        key="health",
        translation_key="health",
        device_class=SensorDeviceClass.ENUM,
        options=list(HEALTH.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_health,
    ),
    _count(
        "jobs_failed",
        lambda data: sum(kind.failed for kind in data.jobs.kinds),
        diagnostic=True,
    ),
    _count("jobs_due", lambda data: sum(kind.due for kind in data.jobs.kinds), diagnostic=True),
    LektoSensorEntityDescription(
        key="worker_last_started",
        translation_key="worker_last_started",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda data: data.jobs.last_started_at,
    ),
    LektoSensorEntityDescription(
        key="search_queued",
        translation_key="search_queued",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.search.queued if data.search else None,
        available=lambda data: data.search is not None,
    ),
    LektoSensorEntityDescription(
        key="classifier_confirmed_since",
        translation_key="classifier_confirmed_since",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda data: data.classifier.since if data.classifier else None,
        available=lambda data: data.classifier is not None,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: LektoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors of the instance."""
    async_add_entities(LektoSensor(entry.runtime_data, description) for description in SENSORS)


class LektoSensor(LektoEntity, SensorEntity):
    """A number of the household's documents, or a state of Lekto."""

    entity_description: LektoSensorEntityDescription

    def __init__(
        self, coordinator: LektoCoordinator, description: LektoSensorEntityDescription
    ) -> None:
        """Make the sensor of ``description``."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Whether Lekto answered, and has the service the sensor reads."""
        return super().available and self.entity_description.available(self.coordinator.data)

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the sensor's value from the coordinator's latest numbers."""
        return self.entity_description.value(self.coordinator.data)
