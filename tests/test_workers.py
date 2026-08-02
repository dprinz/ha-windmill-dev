"""Tests for the Windmill worker-group and worker-instance entities."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.windmill.api import (
    CapabilityAvailability,
    CapabilityReason,
    CapabilityStatus,
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillConnectionError,
    WindmillWorker,
)
from custom_components.windmill.const import (
    DOMAIN,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
    OPT_WORKER_DETAILS,
    OPT_WORKER_GROUPS,
)
from tests.test_health import CONNECTION, ENTRY_DATA, WORKSPACE, _capabilities

UNAUTHORIZED = CapabilityAvailability(
    CapabilityStatus.UNAUTHORIZED, CapabilityReason.PERMISSION_DENIED
)
WORKERS = (
    WindmillWorker(
        name="wk-default-host1-abc", instance="host1", group="default", version="1.775.2"
    ),
    WindmillWorker(
        name="wk-default-host1-def", instance="host1", group="default", version="1.775.2"
    ),
    WindmillWorker(name="wk-gpu-host2-ghi", instance="host2", group="gpu", version="1.774.0"),
)
GROUPS = ("default", "gpu", "reporting")
WORKER_OPTIONS = {
    OPT_INSTANCE_HEALTH: False,
    OPT_RUN_OBSERVATION: False,
    OPT_WORKER_GROUPS: True,
    OPT_WORKER_DETAILS: True,
}


def _as_mock(value: Any) -> AsyncMock:
    """Return an asynchronous mock returning or raising the supplied value."""
    if isinstance(value, Exception):
        return AsyncMock(side_effect=value)
    return AsyncMock(return_value=value)


@contextmanager
def patched_client(
    *,
    capabilities: Any = None,
    workers: Any = WORKERS,
    groups: Any = GROUPS,
    jobs: Any = (),
) -> Iterator[dict[str, AsyncMock]]:
    """Patch every Windmill call a worker-enabled config entry performs."""
    mocks = {
        "connect": _as_mock(CONNECTION),
        "capabilities": _as_mock(capabilities if capabilities is not None else _capabilities()),
        "workers": _as_mock(workers),
        "groups": _as_mock(groups),
        "jobs": _as_mock(jobs),
    }
    targets = {
        "connect": "custom_components.windmill.api.WindmillClient.async_connect",
        "capabilities": (
            "custom_components.windmill.api.WindmillClient.async_discover_capabilities"
        ),
        "workers": "custom_components.windmill.api.WindmillInstanceClient.async_list_workers",
        "groups": (
            "custom_components.windmill.api.WindmillInstanceClient.async_list_worker_groups"
        ),
        "jobs": "custom_components.windmill.api.WindmillClient.async_list_jobs",
    }
    with ExitStack() as stack:
        for key, target in targets.items():
            stack.enter_context(patch(target, new=mocks[key]))
        yield mocks


async def _setup_entry(
    hass: HomeAssistant,
    *,
    options: dict[str, bool] | None = None,
    capabilities: Any = None,
    workers: Any = WORKERS,
    groups: Any = GROUPS,
) -> MockConfigEntry:
    """Set up one loaded Windmill entry with worker monitoring options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=WORKSPACE,
        data=ENTRY_DATA,
        options=options if options is not None else WORKER_OPTIONS,
    )
    entry.add_to_hass(hass)
    with patched_client(capabilities=capabilities, workers=workers, groups=groups):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_worker_groups_expose_bounded_counts(hass: HomeAssistant) -> None:
    """Group entities report alive workers and distinct versions."""
    entry = await _setup_entry(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.home_assistant_default_workers").state == "2"
    assert hass.states.get("sensor.home_assistant_default_worker_versions").state == "1"
    assert hass.states.get("sensor.home_assistant_gpu_workers").state == "1"
    assert hass.states.get("sensor.home_assistant_gpu_worker_versions").state == "1"


async def test_configured_group_without_workers_reports_zero(hass: HomeAssistant) -> None:
    """A configured but idle group stays present with a zero count."""
    await _setup_entry(hass)

    assert hass.states.get("sensor.home_assistant_reporting_workers").state == "0"
    assert hass.states.get("sensor.home_assistant_reporting_worker_versions").state == "0"


async def test_version_drift_is_counted(hass: HomeAssistant) -> None:
    """A group running two versions reports the drift as a distinct version count."""
    drifted = (
        *WORKERS,
        WindmillWorker(
            name="wk-default-host3-jkl", instance="host3", group="default", version="1.774.0"
        ),
    )
    await _setup_entry(hass, workers=drifted)

    assert hass.states.get("sensor.home_assistant_default_worker_versions").state == "2"
    assert hass.states.get("sensor.home_assistant_default_workers").state == "3"


async def test_restarted_workers_keep_stable_entities(hass: HomeAssistant) -> None:
    """Renamed worker processes never change the group or instance entity identity."""
    entry = await _setup_entry(hass)
    entity_registry = er.async_get(hass)
    before = {
        registered.unique_id
        for registered in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }

    restarted = (
        WindmillWorker(
            name="wk-default-host1-zzz", instance="host1", group="default", version="1.775.2"
        ),
        WindmillWorker(name="wk-gpu-host2-yyy", instance="host2", group="gpu", version="1.775.2"),
    )
    with patched_client(workers=restarted):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
        await hass.async_block_till_done()

    after = {
        registered.unique_id
        for registered in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }
    assert before == after
    assert hass.states.get("sensor.home_assistant_default_workers").state == "1"
    assert hass.states.get("sensor.home_assistant_workers_on_host1").state == "1"


async def test_worker_details_are_disabled_by_default(hass: HomeAssistant) -> None:
    """Per-instance entities require an explicit opt-in."""
    await _setup_entry(hass, options={OPT_INSTANCE_HEALTH: False, OPT_WORKER_GROUPS: True})

    assert hass.states.get("sensor.home_assistant_default_workers") is not None
    assert hass.states.get("sensor.home_assistant_workers_on_host1") is None


async def test_worker_instance_entities_use_stable_identifiers(hass: HomeAssistant) -> None:
    """Opt-in per-worker monitoring is keyed by the stable worker instance."""
    entry = await _setup_entry(hass)
    entity_registry = er.async_get(hass)

    assert hass.states.get("sensor.home_assistant_workers_on_host1").state == "2"
    assert hass.states.get("sensor.home_assistant_workers_on_host2").state == "1"
    unique_ids = {
        registered.unique_id
        for registered in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }
    assert f"{entry.entry_id}_worker_instance_alive_host1" in unique_ids
    assert not any("abc" in unique_id for unique_id in unique_ids)


async def test_unlistable_groups_fall_back_to_observed_groups(hass: HomeAssistant) -> None:
    """A denied group listing never prevents worker monitoring."""
    await _setup_entry(hass, groups=WindmillAuthorizationError())

    assert hass.states.get("sensor.home_assistant_default_workers").state == "2"
    assert hass.states.get("sensor.home_assistant_reporting_workers") is None


async def test_unauthorized_worker_capability_creates_no_entities(hass: HomeAssistant) -> None:
    """A denied worker listing disables only this feature."""
    entry = await _setup_entry(hass, capabilities=_capabilities(workers=UNAUTHORIZED))

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.home_assistant_default_workers") is None
    assert hass.states.get("sensor.home_assistant_workers_on_host1") is None


async def test_worker_refresh_failure_marks_entities_unavailable(hass: HomeAssistant) -> None:
    """A failing worker refresh degrades the entities instead of the entry."""
    entry = await _setup_entry(hass)

    with patched_client(workers=WindmillConnectionError()):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.home_assistant_default_workers").state == STATE_UNAVAILABLE


async def test_worker_authentication_failure_triggers_reauth(hass: HomeAssistant) -> None:
    """A revoked token during worker polling starts the reauthentication flow."""
    await _setup_entry(hass)

    with patched_client(workers=WindmillAuthenticationError()):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
        await hass.async_block_till_done()

    flows = [
        flow for flow in hass.config_entries.flow.async_progress() if flow["handler"] == DOMAIN
    ]
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_worker_polling_is_shared_and_bounded(hass: HomeAssistant) -> None:
    """One bounded page walk serves every worker entity."""
    await _setup_entry(hass)

    with patched_client() as mocks:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
        await hass.async_block_till_done()

    assert mocks["workers"].await_count == 1
    page = mocks["workers"].await_args.args[0]
    assert (page.page, page.per_page) == (1, 100)


async def test_full_pages_are_walked_until_the_bounded_limit(hass: HomeAssistant) -> None:
    """A deployment with many workers is read through a bounded number of pages."""
    full_page = tuple(
        WindmillWorker(
            name=f"wk-default-host{index}",
            instance=f"host{index}",
            group="default",
            version="1.775.2",
        )
        for index in range(100)
    )
    await _setup_entry(hass, workers=full_page, groups=("default",))

    with patched_client(workers=full_page, groups=("default",)) as mocks:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
        await hass.async_block_till_done()

    assert mocks["workers"].await_count == 5
    assert hass.states.get("sensor.home_assistant_default_workers").state == "500"


@pytest.mark.parametrize(
    "options",
    [
        {OPT_INSTANCE_HEALTH: False, OPT_RUN_OBSERVATION: False},
        {OPT_INSTANCE_HEALTH: False, OPT_RUN_OBSERVATION: False, OPT_WORKER_GROUPS: False},
    ],
)
async def test_worker_monitoring_stays_off_without_opt_in(
    hass: HomeAssistant, options: dict[str, bool]
) -> None:
    """Neither group nor instance entities appear without an explicit opt-in."""
    entry = await _setup_entry(hass, options=options)

    assert entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids("sensor")


async def test_group_listing_authentication_failure_fails_setup(hass: HomeAssistant) -> None:
    """A revoked token while reading worker groups is an authentication failure."""
    entry = await _setup_entry(hass, groups=WindmillAuthenticationError())

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = [
        flow for flow in hass.config_entries.flow.async_progress() if flow["handler"] == DOMAIN
    ]
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]
