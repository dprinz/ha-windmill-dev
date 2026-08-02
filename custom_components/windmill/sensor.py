"""Windmill instance health sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WindmillConfigEntry
from .api import WindmillHealthState
from .entity import WindmillHealthEntity

HEALTH_STATES = [state.value for state in WindmillHealthState]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WindmillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the health sensors the user enabled and the token supports."""
    runtime = entry.runtime_data
    coordinator = runtime.health_coordinator
    if coordinator is None:
        return

    entities: list[WindmillHealthEntity] = [
        WindmillHealthSensor(coordinator, entry.entry_id, entry.title, runtime),
        WindmillAliveWorkersSensor(coordinator, entry.entry_id, entry.title, runtime),
    ]
    if coordinator.detailed:
        entities.extend(
            [
                WindmillPendingJobsSensor(coordinator, entry.entry_id, entry.title, runtime),
                WindmillRunningJobsSensor(coordinator, entry.entry_id, entry.title, runtime),
            ]
        )
    async_add_entities(entities)


class WindmillHealthSensor(WindmillHealthEntity, SensorEntity):
    """Report the overall Windmill health as a bounded enum state."""

    _key = "instance_health"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = HEALTH_STATES

    @property
    def native_value(self) -> str:
        """Return the overall health state of the current snapshot."""
        return self.coordinator.data.status.status.value


class WindmillAliveWorkersSensor(WindmillHealthEntity, SensorEntity):
    """Report how many workers pinged Windmill recently."""

    _key = "alive_workers"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the alive worker count of the coarse health response."""
        return self.coordinator.data.status.workers_alive


class WindmillQueueSensor(WindmillHealthEntity, SensorEntity):
    """Base class for queue counts that only detailed health provides."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self) -> bool:
        """Require a detailed health projection in the current snapshot."""
        return super().available and self.coordinator.data.detailed is not None


class WindmillPendingJobsSensor(WindmillQueueSensor):
    """Report the number of queued jobs waiting for a worker."""

    _key = "pending_jobs"

    @property
    def native_value(self) -> int | None:
        """Return the pending job count of the detailed health response."""
        detailed = self.coordinator.data.detailed
        return None if detailed is None else detailed.pending_jobs


class WindmillRunningJobsSensor(WindmillQueueSensor):
    """Report the number of jobs currently running."""

    _key = "running_jobs"

    @property
    def native_value(self) -> int | None:
        """Return the running job count of the detailed health response."""
        detailed = self.coordinator.data.detailed
        return None if detailed is None else detailed.running_jobs
