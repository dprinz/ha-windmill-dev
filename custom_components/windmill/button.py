"""Optional buttons for selected parameterless Windmill runnables."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WindmillConfigEntry
from .const import FEATURE_DEFAULTS, OPT_RUNNABLE_BUTTONS
from .coordinator import ResolvedRunnable, WindmillRunnableCoordinator
from .entity import build_device_info
from .models import WindmillRuntimeData
from .services import async_start_runnable


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WindmillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one button per selected parameterless runnable when the user opted in."""
    runtime = entry.runtime_data
    coordinator = runtime.runnable_coordinator
    if coordinator is None or not bool(
        entry.options.get(OPT_RUNNABLE_BUTTONS, FEATURE_DEFAULTS[OPT_RUNNABLE_BUTTONS])
    ):
        return

    async_add_entities(
        WindmillRunnableButton(coordinator, entry, runtime, key)
        for key, resolved in sorted(coordinator.data.items())
        if _is_parameterless(resolved)
    )


def _is_parameterless(resolved: ResolvedRunnable) -> bool:
    """Return whether a runnable can be started without any argument."""
    return resolved.executable and resolved.details is not None and not resolved.details.parameters


class WindmillRunnableButton(CoordinatorEntity[WindmillRunnableCoordinator], ButtonEntity):
    """Start one selected parameterless runnable."""

    _attr_has_entity_name = True
    _attr_translation_key = "run_runnable"

    def __init__(
        self,
        coordinator: WindmillRunnableCoordinator,
        entry: WindmillConfigEntry,
        runtime: WindmillRuntimeData,
        key: tuple[str, str],
    ) -> None:
        """Bind the button to one selected runnable of this config entry."""
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_run_{key[0]}_{key[1]}"
        self._attr_translation_placeholders = {"path": key[1]}
        self._attr_device_info = build_device_info(entry.entry_id, entry.title, runtime)

    @property
    def available(self) -> bool:
        """Require the runnable to stay selected, available and supported."""
        resolved = self.coordinator.data.get(self._key)
        return super().available and resolved is not None and resolved.executable

    async def async_press(self) -> None:
        """Start the runnable asynchronously and discard the job identifier."""
        resolved = self.coordinator.data[self._key]
        await async_start_runnable(self._entry, resolved, {})
