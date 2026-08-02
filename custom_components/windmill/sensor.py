"""Windmill instance health sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WindmillConfigEntry
from .api import WindmillHealthState
from .const import FEATURE_DEFAULTS, OPT_WORKER_DETAILS, OPT_WORKER_GROUPS
from .entity import WindmillHealthEntity, WindmillWorkerEntity
from .models import WindmillRuntimeData

HEALTH_STATES = [state.value for state in WindmillHealthState]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WindmillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors the user enabled and the token supports."""
    runtime = entry.runtime_data
    entities: list[SensorEntity] = []
    entities.extend(_health_sensors(entry, runtime))
    entities.extend(_worker_sensors(entry, runtime))
    async_add_entities(entities)


def _health_sensors(entry: WindmillConfigEntry, runtime: WindmillRuntimeData) -> list[SensorEntity]:
    """Build the health sensors of one config entry."""
    coordinator = runtime.health_coordinator
    if coordinator is None:
        return []
    sensors: list[SensorEntity] = [
        WindmillHealthSensor(coordinator, entry.entry_id, entry.title, runtime),
        WindmillAliveWorkersSensor(coordinator, entry.entry_id, entry.title, runtime),
    ]
    if coordinator.detailed:
        sensors.extend(
            [
                WindmillPendingJobsSensor(coordinator, entry.entry_id, entry.title, runtime),
                WindmillRunningJobsSensor(coordinator, entry.entry_id, entry.title, runtime),
            ]
        )
    return sensors


def _worker_sensors(entry: WindmillConfigEntry, runtime: WindmillRuntimeData) -> list[SensorEntity]:
    """Build the worker-group and opt-in per-instance sensors."""
    coordinator = runtime.worker_coordinator
    if coordinator is None:
        return []

    sensors: list[SensorEntity] = []
    if _enabled(entry, OPT_WORKER_GROUPS):
        for group in sorted(coordinator.data.groups):
            sensors.append(
                WindmillWorkerGroupSensor(coordinator, entry.entry_id, entry.title, runtime, group)
            )
            sensors.append(
                WindmillWorkerVersionSensor(
                    coordinator, entry.entry_id, entry.title, runtime, group
                )
            )
    if _enabled(entry, OPT_WORKER_DETAILS):
        sensors.extend(
            WindmillWorkerInstanceSensor(
                coordinator, entry.entry_id, entry.title, runtime, instance
            )
            for instance in sorted(coordinator.data.instances)
        )
    return sensors


def _enabled(entry: WindmillConfigEntry, option: str) -> bool:
    """Return whether an opt-in feature is enabled for this config entry."""
    return bool(entry.options.get(option, FEATURE_DEFAULTS[option]))


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


class WindmillWorkerGroupSensor(WindmillWorkerEntity, SensorEntity):
    """Report how many workers of one group pinged Windmill recently."""

    _key = "worker_group_alive"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return zero for a configured but idle group instead of an unknown state."""
        group = self.coordinator.data.groups.get(self._subject)
        return 0 if group is None else group.alive_workers


class WindmillWorkerVersionSensor(WindmillWorkerEntity, SensorEntity):
    """Report how many distinct worker versions one group currently runs."""

    _key = "worker_group_versions"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the distinct version count; anything above one means version drift."""
        group = self.coordinator.data.groups.get(self._subject)
        return 0 if group is None else group.versions


class WindmillWorkerInstanceSensor(WindmillWorkerEntity, SensorEntity):
    """Report how many worker processes one worker instance currently runs."""

    _key = "worker_instance_alive"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return zero once an instance stops reporting instead of removing the entity."""
        return self.coordinator.data.instances.get(self._subject, 0)
