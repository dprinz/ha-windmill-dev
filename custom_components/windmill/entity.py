"""Shared device and entity plumbing for Windmill platforms."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WindmillHealthCoordinator
from .models import WindmillRuntimeData


def build_device_info(entry_id: str, title: str, runtime: WindmillRuntimeData) -> DeviceInfo:
    """Describe the configured Windmill workspace as one service device."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Windmill",
        model=runtime.server.edition.upper(),
        name=title,
        sw_version=runtime.server.version,
        configuration_url=runtime.client.base_url,
    )


class WindmillHealthEntity(CoordinatorEntity[WindmillHealthCoordinator]):
    """Base entity for values derived from one shared health snapshot."""

    _attr_has_entity_name = True
    _key: str

    def __init__(
        self,
        coordinator: WindmillHealthCoordinator,
        entry_id: str,
        title: str,
        runtime: WindmillRuntimeData,
    ) -> None:
        """Attach the entity to the shared coordinator and the instance device."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{self._key}"
        self._attr_translation_key = self._key
        self._attr_device_info = build_device_info(entry_id, title, runtime)
