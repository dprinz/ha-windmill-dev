"""Windmill instance health sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WindmillConfigEntry
from .api import JobState, WindmillHealthState
from .const import FEATURE_DEFAULTS, OPT_WORKER_DETAILS, OPT_WORKER_GROUPS
from .entity import (
    WindmillHealthEntity,
    WindmillRunEntity,
    WindmillRunnableRunEntity,
    WindmillWorkerEntity,
)
from .models import WindmillRuntimeData

HEALTH_STATES = [state.value for state in WindmillHealthState]
# A "last status" is by definition the outcome of a finished run, so the enum omits the two
# states a job passes through on its way there.
COMPLETION_STATES = [
    state.value for state in (JobState.SUCCESS, JobState.FAILURE, JobState.CANCELED)
]


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
    entities.extend(_run_sensors(entry, runtime))
    entities.extend(_runnable_run_sensors(entry, runtime))
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


def _run_sensors(entry: WindmillConfigEntry, runtime: WindmillRuntimeData) -> list[SensorEntity]:
    """Build the aggregate run sensors; runs never get one entity per job."""
    coordinator = runtime.run_coordinator
    if coordinator is None:
        return []
    return [
        WindmillRunningRunsSensor(coordinator, entry.entry_id, entry.title, runtime),
        WindmillQueuedRunsSensor(coordinator, entry.entry_id, entry.title, runtime),
        WindmillLastSuccessSensor(coordinator, entry.entry_id, entry.title, runtime),
        WindmillLastFailureSensor(coordinator, entry.entry_id, entry.title, runtime),
    ]


def _runnable_run_sensors(
    entry: WindmillConfigEntry, runtime: WindmillRuntimeData
) -> list[SensorEntity]:
    """Build the per-runnable detail sensors of every explicitly selected runnable."""
    coordinator = runtime.runnable_run_coordinator
    if coordinator is None:
        return []
    return [
        sensor(coordinator, entry.entry_id, runtime, selection)
        for selection in coordinator.selections
        for sensor in (
            WindmillRunnableLastRunSensor,
            WindmillRunnableLastStatusSensor,
            WindmillRunnableLastDurationSensor,
            WindmillRunnableNextRunSensor,
        )
    ]


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


class WindmillRunningRunsSensor(WindmillRunEntity, SensorEntity):
    """Report how many observed top-level jobs are currently running."""

    _key = "workspace_running_jobs"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the running job count of the observed window."""
        return self.coordinator.data.running


class WindmillQueuedRunsSensor(WindmillRunEntity, SensorEntity):
    """Report how many observed top-level jobs are waiting to start."""

    _key = "workspace_queued_jobs"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the queued job count of the observed window."""
        return self.coordinator.data.queued


class WindmillLastSuccessSensor(WindmillRunEntity, SensorEntity):
    """Report when a top-level job last completed successfully."""

    _key = "last_successful_run"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the monotonic last successful completion timestamp."""
        return self.coordinator.data.last_success


class WindmillLastFailureSensor(WindmillRunEntity, SensorEntity):
    """Report when a top-level job last failed."""

    _key = "last_failed_run"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the monotonic last failed completion timestamp."""
        return self.coordinator.data.last_failure


class WindmillRunnableLastRunSensor(WindmillRunnableRunEntity, SensorEntity):
    """Report when one selected runnable last finished a run."""

    _key = "runnable_last_run"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the completion timestamp of this runnable's last run."""
        return self.state_of_runs.last_run


class WindmillRunnableNextRunSensor(WindmillRunnableRunEntity, SensorEntity):
    """Report when one selected runnable is scheduled to run next."""

    _key = "runnable_next_run"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the reserved slot of the next run, or nothing without a schedule."""
        return self.state_of_runs.next_run


class WindmillRunnableLastStatusSensor(WindmillRunnableRunEntity, SensorEntity):
    """Report how one selected runnable's last run ended."""

    _key = "runnable_last_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = COMPLETION_STATES

    @property
    def native_value(self) -> str | None:
        """Return the outcome of the last run, or nothing before one was observed."""
        state = self.state_of_runs.last_state
        return None if state is None else state.value


class WindmillRunnableLastDurationSensor(WindmillRunnableRunEntity, SensorEntity):
    """Report how long one selected runnable's last run took."""

    _key = "runnable_last_duration"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return the last run's duration in seconds; Windmill reports milliseconds."""
        duration = self.state_of_runs.last_duration_ms
        return None if duration is None else duration / 1000
