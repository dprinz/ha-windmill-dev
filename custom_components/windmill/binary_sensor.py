"""Windmill instance health binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WindmillConfigEntry
from .entity import WindmillHealthEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WindmillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the database connectivity sensor when health monitoring is enabled."""
    runtime = entry.runtime_data
    coordinator = runtime.health_coordinator
    if coordinator is None:
        return
    async_add_entities(
        [WindmillDatabaseBinarySensor(coordinator, entry.entry_id, entry.title, runtime)]
    )


class WindmillDatabaseBinarySensor(WindmillHealthEntity, BinarySensorEntity):
    """Report whether Windmill can currently reach its database."""

    _key = "database"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return whether the coarse health response reports a healthy database."""
        return self.coordinator.data.status.database_healthy
