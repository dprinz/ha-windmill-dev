"""Tests for actionable Windmill repair issues."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.windmill.api import (
    CapabilityAvailability,
    CapabilityReason,
    CapabilityStatus,
    WindmillConnectionError,
    WindmillWorker,
)
from custom_components.windmill.const import (
    DOMAIN,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
    OPT_UPDATE_ENTITY,
    OPT_WORKER_DETAILS,
    OPT_WORKER_GROUPS,
    WORKER_DRIFT_GRACE_MINUTES,
)
from tests.test_health import UNAUTHORIZED, _capabilities
from tests.test_health import _setup_entry as _setup_health_entry
from tests.test_health import patched_client as patched_health_client
from tests.test_workers import WORKERS
from tests.test_workers import _setup_entry as _setup_worker_entry
from tests.test_workers import patched_client as patched_worker_client

UNSUPPORTED = CapabilityAvailability(
    CapabilityStatus.UNSUPPORTED, CapabilityReason.ENDPOINT_MISSING
)
TEMPORARY = CapabilityAvailability(
    CapabilityStatus.TEMPORARILY_UNAVAILABLE, CapabilityReason.TEMPORARY_FAILURE
)
DRIFTED = (
    *WORKERS,
    WindmillWorker(
        name="wk-default-host3-jkl", instance="host3", group="default", version="1.774.0"
    ),
)


def _issues(hass: HomeAssistant) -> dict[str, ir.IssueEntry]:
    """Return every Windmill issue keyed by the part after the entry identifier."""
    registry = ir.async_get(hass)
    return {
        issue.issue_id.split("_", 1)[1]: issue
        for issue in registry.issues.values()
        if issue.domain == DOMAIN
    }


async def test_denied_permission_for_an_enabled_feature_is_reported(hass: HomeAssistant) -> None:
    """An enabled feature whose capability is denied produces one actionable issue."""
    await _setup_health_entry(
        hass,
        capabilities=_capabilities(health=UNAUTHORIZED),
        options={OPT_INSTANCE_HEALTH: True, OPT_RUN_OBSERVATION: False},
    )

    issue = _issues(hass)["instance_health_health"]
    assert issue.translation_key == "missing_permission"
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.is_fixable is False
    assert issue.translation_placeholders == {
        "feature": "instance_health",
        "capability": "health",
    }


async def test_unsupported_capability_for_an_enabled_feature_is_reported(
    hass: HomeAssistant,
) -> None:
    """A feature the server does not offer is reported separately from a denied permission."""
    await _setup_health_entry(
        hass,
        capabilities=_capabilities(update_visibility=UNSUPPORTED),
        options={OPT_INSTANCE_HEALTH: False, OPT_RUN_OBSERVATION: False, OPT_UPDATE_ENTITY: True},
    )

    assert _issues(hass)["update_entity_update_visibility"].translation_key == (
        "unsupported_capability"
    )


async def test_transient_and_disabled_features_create_no_issue(hass: HomeAssistant) -> None:
    """A temporary outage is not a repair, and a disabled feature is not broken."""
    await _setup_health_entry(
        hass,
        capabilities=_capabilities(health=TEMPORARY, runs=UNAUTHORIZED),
        options={OPT_INSTANCE_HEALTH: True, OPT_RUN_OBSERVATION: False},
    )

    assert _issues(hass) == {}


async def test_issue_disappears_once_the_permission_works(hass: HomeAssistant) -> None:
    """A recovered capability removes the issue without any user action."""
    entry = await _setup_health_entry(
        hass,
        capabilities=_capabilities(health=UNAUTHORIZED),
        options={OPT_INSTANCE_HEALTH: True, OPT_RUN_OBSERVATION: False},
    )

    assert "instance_health_health" in _issues(hass)

    entry.runtime_data.capability_coordinator.async_set_updated_data(_capabilities())
    await hass.async_block_till_done()

    assert _issues(hass) == {}


async def test_capabilities_are_re_probed_so_an_issue_can_clear_itself(
    hass: HomeAssistant,
) -> None:
    """The issue listener keeps the capability coordinator polling, so no reload is needed."""
    await _setup_health_entry(
        hass,
        capabilities=_capabilities(health=UNAUTHORIZED),
        options={OPT_INSTANCE_HEALTH: True, OPT_RUN_OBSERVATION: False},
    )

    assert "instance_health_health" in _issues(hass)

    with patched_health_client() as mocks:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=7))
        await hass.async_block_till_done()

    assert mocks["capabilities"].await_count == 1
    assert _issues(hass) == {}


async def test_issues_are_deleted_when_the_entry_unloads(hass: HomeAssistant) -> None:
    """An unloaded entry cannot substantiate a warning."""
    entry = await _setup_health_entry(
        hass,
        capabilities=_capabilities(health=UNAUTHORIZED),
        options={OPT_INSTANCE_HEALTH: True, OPT_RUN_OBSERVATION: False},
    )

    assert "instance_health_health" in _issues(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert _issues(hass) == {}


async def test_worker_version_drift_needs_to_persist(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A rolling upgrade creates no issue; drift that lasts does, and it clears on its own."""
    await _setup_worker_entry(hass, workers=DRIFTED)

    assert _issues(hass) == {}

    with patched_worker_client(workers=DRIFTED):
        freezer.tick(timedelta(minutes=WORKER_DRIFT_GRACE_MINUTES + 1))
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
        await hass.async_block_till_done()

    issue = _issues(hass)["worker_versions_default"]
    assert issue.translation_key == "worker_version_drift"
    assert issue.translation_placeholders == {"group": "default", "versions": "2"}

    with patched_worker_client(workers=WORKERS):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
        await hass.async_block_till_done()

    assert _issues(hass) == {}


async def test_failed_worker_poll_does_not_report_drift(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A failed poll keeps the previous snapshot, which is not evidence of current drift."""
    await _setup_worker_entry(
        hass,
        workers=DRIFTED,
        options={
            OPT_INSTANCE_HEALTH: False,
            OPT_RUN_OBSERVATION: False,
            OPT_WORKER_GROUPS: True,
            OPT_WORKER_DETAILS: False,
        },
    )

    with patched_worker_client(workers=WindmillConnectionError()):
        freezer.tick(timedelta(minutes=WORKER_DRIFT_GRACE_MINUTES + 1))
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
        await hass.async_block_till_done()

    assert _issues(hass) == {}


async def test_failed_worker_poll_keeps_an_existing_drift_issue(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A failed poll is "unknown", not "resolved"; only a successful poll clears the issue."""
    await _setup_worker_entry(hass, workers=DRIFTED)

    with patched_worker_client(workers=DRIFTED):
        freezer.tick(timedelta(minutes=WORKER_DRIFT_GRACE_MINUTES + 1))
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
        await hass.async_block_till_done()

    assert "worker_versions_default" in _issues(hass)

    with patched_worker_client(workers=WindmillConnectionError()):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
        await hass.async_block_till_done()

    assert "worker_versions_default" in _issues(hass)

    with patched_worker_client(workers=WORKERS):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=9))
        await hass.async_block_till_done()

    assert _issues(hass) == {}


async def test_failed_worker_poll_does_not_restart_the_drift_grace_timer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A failed poll during the grace period must not restart the drift observation."""
    await _setup_worker_entry(hass, workers=DRIFTED)

    with patched_worker_client(workers=WindmillConnectionError()):
        freezer.tick(timedelta(minutes=WORKER_DRIFT_GRACE_MINUTES - 10))
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
        await hass.async_block_till_done()

    assert _issues(hass) == {}

    with patched_worker_client(workers=DRIFTED):
        freezer.tick(timedelta(minutes=11))
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
        await hass.async_block_till_done()

    assert "worker_versions_default" in _issues(hass)
