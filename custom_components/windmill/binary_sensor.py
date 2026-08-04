"""Windmill instance health and per-runnable binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WindmillConfigEntry
from .entity import WindmillHealthEntity, WindmillRunnableRunEntity
from .models import WindmillRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WindmillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the health and per-runnable binary sensors the user enabled."""
    runtime = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    coordinator = runtime.health_coordinator
    if coordinator is not None:
        entities.append(
            WindmillDatabaseBinarySensor(coordinator, entry.entry_id, entry.title, runtime)
        )
    entities.extend(_runnable_running_sensors(entry, runtime))
    async_add_entities(entities)


def _runnable_running_sensors(
    entry: WindmillConfigEntry, runtime: WindmillRuntimeData
) -> list[BinarySensorEntity]:
    """Build one running sensor per explicitly selected runnable."""
    coordinator = runtime.runnable_run_coordinator
    if coordinator is None:
        return []
    return [
        WindmillRunnableRunningBinarySensor(coordinator, entry.entry_id, runtime, selection)
        for selection in coordinator.selections
    ]


class WindmillDatabaseBinarySensor(WindmillHealthEntity, BinarySensorEntity):
    """Report whether Windmill can currently reach its database."""

    _key = "database"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return whether the coarse health response reports a healthy database."""
        return self.coordinator.data.status.database_healthy


class WindmillRunnableRunningBinarySensor(WindmillRunnableRunEntity, BinarySensorEntity):
    """Report whether one selected runnable is executing right now."""

    _key = "runnable_running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool:
        """Return whether a job of this runnable is currently running."""
        return self.state_of_runs.running
