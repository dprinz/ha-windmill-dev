"""Shared device and entity plumbing for Windmill platforms."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    RunnableRunState,
    RunnableSelection,
    WindmillHealthCoordinator,
    WindmillRunCoordinator,
    WindmillRunnableRunCoordinator,
    WindmillWorkerCoordinator,
)
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


def build_runnable_device_info(entry_id: str, selection: RunnableSelection) -> DeviceInfo:
    """Describe one selected runnable as its own device below the workspace.

    A device per runnable is what makes a per-job dashboard card possible. Its existence
    follows the user's explicit selection, never Windmill's runtime state, so it appears and
    disappears only when the selection is changed.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{selection.kind.value}_{selection.path}")},
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Windmill",
        model=selection.kind.value.capitalize(),
        name=selection.path,
        via_device=(DOMAIN, entry_id),
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
        self.runtime = runtime
        self._attr_unique_id = f"{entry_id}_{self._key}"
        self._attr_translation_key = self._key
        self._attr_device_info = build_device_info(entry_id, title, runtime)


class WindmillWorkerEntity(CoordinatorEntity[WindmillWorkerCoordinator]):
    """Base entity for values derived from one shared worker snapshot."""

    _attr_has_entity_name = True
    _key: str

    def __init__(
        self,
        coordinator: WindmillWorkerCoordinator,
        entry_id: str,
        title: str,
        runtime: WindmillRuntimeData,
        subject: str,
    ) -> None:
        """Attach the entity to one stable worker group or worker instance."""
        super().__init__(coordinator)
        self._subject = subject
        self._attr_unique_id = f"{entry_id}_{self._key}_{subject}"
        self._attr_translation_key = self._key
        self._attr_translation_placeholders = {"subject": subject}
        self._attr_device_info = build_device_info(entry_id, title, runtime)


class WindmillRunnableRunEntity(CoordinatorEntity[WindmillRunnableRunCoordinator]):
    """Base entity for the run details of one explicitly selected runnable."""

    _attr_has_entity_name = True
    _key: str

    def __init__(
        self,
        coordinator: WindmillRunnableRunCoordinator,
        entry_id: str,
        runtime: WindmillRuntimeData,
        selection: RunnableSelection,
    ) -> None:
        """Bind the entity to one selection and its own device."""
        super().__init__(coordinator)
        self.runtime = runtime
        self._selection = selection
        self._attr_unique_id = f"{entry_id}_{self._key}_{selection.kind.value}_{selection.path}"
        self._attr_translation_key = self._key
        self._attr_device_info = build_runnable_device_info(entry_id, selection)

    @property
    def state_of_runs(self) -> RunnableRunState:
        """Return what is currently known about this runnable's runs."""
        return self.coordinator.data.get(self._selection.key, RunnableRunState())

    @property
    def available(self) -> bool:
        """Require the runnable to still resolve against the workspace.

        The job read cannot answer this: a path that no longer exists simply has no jobs, which
        is indistinguishable from one that never ran. The selection resolution is the only
        source that separates "gone or forbidden" from "idle".
        """
        if not super().available:
            return False
        resolver = self.runtime.runnable_coordinator
        if resolver is None:
            return True
        resolved = resolver.data.get(self._selection.key)
        return resolved is None or resolved.available


class WindmillRunEntity(CoordinatorEntity[WindmillRunCoordinator]):
    """Base entity for values derived from one shared run snapshot."""

    _attr_has_entity_name = True
    _key: str

    def __init__(
        self,
        coordinator: WindmillRunCoordinator,
        entry_id: str,
        title: str,
        runtime: WindmillRuntimeData,
    ) -> None:
        """Attach the entity to the shared coordinator and the instance device."""
        super().__init__(coordinator)
        self.runtime = runtime
        self._attr_unique_id = f"{entry_id}_{self._key}"
        self._attr_translation_key = self._key
        self._attr_device_info = build_device_info(entry_id, title, runtime)
