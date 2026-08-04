"""Redacted diagnostics for one Windmill config entry.

The payload is built from an explicit allowlist of bounded metadata. Nothing is serialized by
dumping an object, so a field that is added later cannot leak into a download by accident.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import WindmillConfigEntry
from .api import CapabilityMatrix, is_managed_cloud
from .const import (
    CONF_BASE_URL,
    CONF_TOKEN,
    CONF_WORKSPACE,
    FEATURE_DEFAULTS,
    FEATURE_OPTIONS,
    OPT_RUNNABLES,
)
from .coordinator import load_selections

TO_REDACT = {CONF_TOKEN, CONF_BASE_URL, CONF_WORKSPACE, "title", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WindmillConfigEntry
) -> dict[str, Any]:
    """Return bounded, redacted diagnostics for one Windmill config entry."""
    runtime = entry.runtime_data
    selections = load_selections(entry.options.get(OPT_RUNNABLES))
    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "unique_id": entry.unique_id,
                "version": entry.version,
                "source": entry.source,
                "state": entry.state.value,
                "data_keys": sorted(entry.data),
            },
            "instance": {
                # The URL itself is redacted; only the shape of the deployment is reported.
                CONF_BASE_URL: entry.data.get(CONF_BASE_URL),
                "managed_cloud": is_managed_cloud(runtime.client.base_url),
                "edition": runtime.server.edition.value,
                "version": runtime.server.version,
                "is_admin": runtime.identity.is_admin,
                "is_super_admin": runtime.identity.is_super_admin,
            },
            "options": {
                **{
                    option: bool(entry.options.get(option, FEATURE_DEFAULTS[option]))
                    for option in FEATURE_OPTIONS
                },
                "selected_runnables": len(selections),
                "selection_modes": sorted({selection.mode.value for selection in selections}),
            },
            "capabilities": _capabilities(runtime.capabilities),
            "coordinators": {
                name: _coordinator(coordinator)
                for name, coordinator in (
                    ("capabilities", runtime.capability_coordinator),
                    ("health", runtime.health_coordinator),
                    ("workers", runtime.worker_coordinator),
                    ("runs", runtime.run_coordinator),
                    ("runnables", runtime.runnable_coordinator),
                    ("runnable_runs", runtime.runnable_run_coordinator),
                    ("update", runtime.update_coordinator),
                )
            },
            "started_jobs": {
                "tracked": 0 if runtime.started_jobs is None else len(runtime.started_jobs.tracked)
            },
        },
        TO_REDACT,
    )


def _capabilities(capabilities: CapabilityMatrix) -> dict[str, dict[str, str]]:
    """Report every capability as its status and bounded reason."""
    reported = {}
    for field in fields(capabilities):
        availability = getattr(capabilities, field.name)
        reported[field.name] = {
            "status": availability.status.value,
            "reason": availability.reason.value,
        }
    return reported


def _coordinator(coordinator: DataUpdateCoordinator[Any] | None) -> dict[str, Any]:
    """Report one coordinator's liveness without any observed payload."""
    if coordinator is None:
        return {"enabled": False}
    interval = coordinator.update_interval
    return {
        "enabled": True,
        "last_update_success": coordinator.last_update_success,
        "update_interval_seconds": None if interval is None else interval.total_seconds(),
    }
