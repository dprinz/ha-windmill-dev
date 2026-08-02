"""Read-only update visibility for self-hosted Windmill deployments."""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WindmillConfigEntry
from .api import release_url
from .coordinator import WindmillUpdateCoordinator
from .entity import build_device_info
from .models import WindmillRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WindmillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the update entity for an eligible self-hosted deployment."""
    runtime = entry.runtime_data
    coordinator = runtime.update_coordinator
    if coordinator is None:
        return
    async_add_entities([WindmillUpdateEntity(coordinator, entry.entry_id, entry.title, runtime)])


class WindmillUpdateEntity(CoordinatorEntity[WindmillUpdateCoordinator], UpdateEntity):
    """Report installed and latest Windmill versions without offering an install."""

    _attr_has_entity_name = True
    _attr_translation_key = "server"
    _attr_auto_update = False

    def __init__(
        self,
        coordinator: WindmillUpdateCoordinator,
        entry_id: str,
        title: str,
        runtime: WindmillRuntimeData,
    ) -> None:
        """Bind the entity to the shared update coordinator and the instance device."""
        super().__init__(coordinator)
        self._runtime = runtime
        self._attr_unique_id = f"{entry_id}_server_update"
        self._attr_device_info = build_device_info(entry_id, title, runtime)

    @property
    def installed_version(self) -> str | None:
        """Return the version the connected deployment reports."""
        status = self.coordinator.data
        if status is not None and status.installed_version is not None:
            return status.installed_version
        return self._runtime.server.version

    @property
    def latest_version(self) -> str | None:
        """Return the latest version, or the installed one when up to date."""
        status = self.coordinator.data
        if status is None:
            return None
        if status.up_to_date:
            return self.installed_version
        return status.latest_version

    @property
    def release_url(self) -> str | None:
        """Return the upstream release page only for a safely formatted version."""
        return release_url(self.latest_version)
