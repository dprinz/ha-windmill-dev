"""Actionable repair issues derived from capabilities and worker observations.

An issue is created only for a condition a user can act on and that is not transient. A capability
that is `temporarily_unavailable` is an outage, not a repair, and worker version drift is normal
during a rolling upgrade, so it must persist before it becomes an issue.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .api import CapabilityAvailability, CapabilityStatus
from .const import (
    DOMAIN,
    FEATURE_DEFAULTS,
    OPT_DETAILED_HEALTH,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
    OPT_UPDATE_ENTITY,
    OPT_WORKER_DETAILS,
    OPT_WORKER_GROUPS,
    WORKER_DRIFT_GRACE_MINUTES,
)
from .models import WindmillRuntimeData

# One enabled feature and the capability that must hold for it. A feature the user did not enable
# never produces an issue, because nothing is broken for that user.
FEATURE_CAPABILITIES: tuple[tuple[str, str], ...] = (
    (OPT_INSTANCE_HEALTH, "health"),
    (OPT_DETAILED_HEALTH, "detailed_health"),
    (OPT_WORKER_GROUPS, "workers"),
    (OPT_WORKER_DETAILS, "workers"),
    (OPT_RUN_OBSERVATION, "runs"),
    (OPT_UPDATE_ENTITY, "update_visibility"),
)

_ACTIONABLE = {
    CapabilityStatus.UNAUTHORIZED: "missing_permission",
    CapabilityStatus.UNSUPPORTED: "unsupported_capability",
}


@callback
def async_evaluate_issues(
    hass: HomeAssistant,
    entry_id: str,
    options: Mapping[str, Any],
    runtime: WindmillRuntimeData,
    drift_since: dict[str, datetime],
) -> None:
    """Create, keep or delete every issue this config entry owns."""
    _async_capability_issues(hass, entry_id, options, runtime)
    _async_worker_drift_issue(hass, entry_id, runtime, drift_since)


@callback
def async_delete_issues(hass: HomeAssistant, entry_id: str) -> None:
    """Delete every issue of one config entry, whatever its current condition is."""
    registry = ir.async_get(hass)
    for issue in list(registry.issues.values()):
        if issue.domain == DOMAIN and issue.issue_id.startswith(f"{entry_id}_"):
            ir.async_delete_issue(hass, DOMAIN, issue.issue_id)


@callback
def _async_capability_issues(
    hass: HomeAssistant, entry_id: str, options: Mapping[str, Any], runtime: WindmillRuntimeData
) -> None:
    """Report every enabled feature whose capability is denied or unsupported."""
    capabilities = runtime.capabilities
    for option, capability in FEATURE_CAPABILITIES:
        issue_id = f"{entry_id}_{option}_{capability}"
        availability: CapabilityAvailability = getattr(capabilities, capability)
        enabled = bool(options.get(option, FEATURE_DEFAULTS[option]))
        key = _ACTIONABLE.get(availability.status) if enabled else None
        if key is None:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=key,
            translation_placeholders={"feature": option, "capability": capability},
        )


@callback
def _async_worker_drift_issue(
    hass: HomeAssistant,
    entry_id: str,
    runtime: WindmillRuntimeData,
    drift_since: dict[str, datetime],
) -> None:
    """Report worker groups that have been running several versions for long enough."""
    coordinator = runtime.worker_coordinator
    if coordinator is None or not coordinator.last_update_success:
        # A failed poll carries the previous snapshot: drift is unknown, not resolved, so
        # neither the issues nor their grace timers may change.
        return
    observed = {group: state.versions for group, state in coordinator.data.groups.items()}
    now = dt_util.utcnow()
    for group in set(drift_since) | set(observed):
        issue_id = f"{entry_id}_worker_versions_{group}"
        if observed.get(group, 0) <= 1:
            drift_since.pop(group, None)
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue
        first_seen = drift_since.setdefault(group, now)
        if now - first_seen < timedelta(minutes=WORKER_DRIFT_GRACE_MINUTES):
            # A rolling upgrade runs two versions for a while; that is not a repair.
            continue
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="worker_version_drift",
            translation_placeholders={"group": group, "versions": str(observed[group])},
        )
