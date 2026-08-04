"""Tests for the per-runnable run detail entities."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.windmill.api import (
    AddressingMode,
    CapabilityAvailability,
    CapabilityReason,
    CapabilityStatus,
    JobState,
    RunnableDetails,
    RunnableKind,
    WindmillAuthenticationError,
    WindmillJob,
    WindmillNotFoundError,
    WindmillRateLimitError,
    WindmillRunnable,
)
from custom_components.windmill.const import (
    DOMAIN,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
    OPT_RUNNABLE_DETAILS,
    OPT_RUNNABLES,
)
from custom_components.windmill.coordinator import (
    RUN_UPDATE_INTERVAL,
    RUNNABLE_RUN_UPDATE_INTERVAL,
    RunnableRunState,
    load_runnable_run_states,
)
from tests.test_health import CONNECTION, ENTRY_DATA, UNSUPPORTED, WORKSPACE, _capabilities

LIGHTS_PATH = "u/automation/lights"
NIGHT_PATH = "f/home/night"
LIGHTS = WindmillRunnable(kind=RunnableKind.SCRIPT, path=LIGHTS_PATH, summary="Toggle")
NIGHT = WindmillRunnable(kind=RunnableKind.FLOW, path=NIGHT_PATH, summary="")
LIGHTS_SELECTION = {
    "kind": "script",
    "path": LIGHTS_PATH,
    "mode": AddressingMode.LATEST.value,
}
NIGHT_SELECTION = {"kind": "flow", "path": NIGHT_PATH, "mode": AddressingMode.LATEST.value}
DETAILS = RunnableDetails(
    kind=RunnableKind.SCRIPT,
    path=LIGHTS_PATH,
    summary="Toggle",
    script_hash="0123456789abcdef",
    flow_version=None,
    parameters=(),
    schema_supported=True,
)
BASE_OPTIONS = {OPT_INSTANCE_HEALTH: False, OPT_RUN_OBSERVATION: False}
# What a single 503, timeout or rate limit on the runs probe leaves behind at setup.
TEMPORARILY_UNAVAILABLE = CapabilityAvailability(
    CapabilityStatus.TEMPORARILY_UNAVAILABLE, CapabilityReason.TEMPORARY_FAILURE
)
YESTERDAY = datetime(2026, 8, 3, 22, 15, tzinfo=UTC)
TODAY = datetime(2026, 8, 4, 6, 30, tzinfo=UTC)

LIGHTS_UNIQUE_IDS = {
    "sensor": ("runnable_last_run", "runnable_last_status", "runnable_last_duration"),
    "binary_sensor": ("runnable_running",),
}


def _completed(
    job_id: str,
    path: str,
    kind: str,
    state: JobState,
    completed_at: datetime,
    duration_ms: int = 1500,
) -> WindmillJob:
    """Build one completed job of a named runnable."""
    return WindmillJob(
        id=job_id,
        state=state,
        kind=kind,
        path=path,
        created_at=completed_at - timedelta(seconds=duration_ms / 1000),
        completed_at=completed_at,
        duration_ms=duration_ms,
    )


def _running(job_id: str, path: str, kind: str) -> WindmillJob:
    """Build one running job of a named runnable."""
    return WindmillJob(
        id=job_id,
        state=JobState.RUNNING,
        kind=kind,
        path=path,
        created_at=TODAY,
        completed_at=None,
        duration_ms=None,
    )


def _as_mock(value: Any) -> AsyncMock:
    """Return an asynchronous mock returning or raising the supplied value."""
    if isinstance(value, Exception):
        return AsyncMock(side_effect=value)
    return AsyncMock(return_value=value)


@contextmanager
def patched_client(
    *,
    capabilities: Any = None,
    runnable_jobs: Any = None,
    jobs: Any = (),
    details: Any = DETAILS,
) -> Iterator[dict[str, AsyncMock]]:
    """Patch every Windmill call a detail-enabled config entry performs."""

    async def per_runnable(path: str, page: Any) -> tuple[WindmillJob, ...]:
        if isinstance(runnable_jobs, Exception):
            raise runnable_jobs
        rows = {} if runnable_jobs is None else runnable_jobs
        return tuple(rows.get(path, ()))

    async def list_runnables(kind: RunnableKind, page: Any) -> tuple[WindmillRunnable, ...]:
        return tuple(row for row in (LIGHTS, NIGHT) if row.kind is kind)

    mocks = {
        "connect": _as_mock(CONNECTION),
        "capabilities": _as_mock(capabilities if capabilities is not None else _capabilities()),
        "runnables": AsyncMock(side_effect=list_runnables),
        "details": _as_mock(details),
        "runnable_jobs": AsyncMock(side_effect=per_runnable),
        "jobs": AsyncMock(side_effect=jobs) if callable(jobs) else _as_mock(jobs),
    }
    targets = {
        "connect": "custom_components.windmill.api.WindmillClient.async_connect",
        "capabilities": (
            "custom_components.windmill.api.WindmillClient.async_discover_capabilities"
        ),
        "runnables": "custom_components.windmill.api.WindmillClient.async_list_runnables",
        "details": "custom_components.windmill.api.WindmillClient.async_get_runnable",
        "runnable_jobs": "custom_components.windmill.api.WindmillClient.async_list_runnable_jobs",
        "jobs": "custom_components.windmill.api.WindmillClient.async_list_jobs",
    }
    with ExitStack() as stack:
        for key, target in targets.items():
            stack.enter_context(patch(target, new=mocks[key]))
        yield mocks


async def _setup_entry(
    hass: HomeAssistant,
    *,
    options: dict[str, Any] | None = None,
    runnable_jobs: Any = None,
    jobs: Any = (),
    capabilities: Any = None,
    details: Any = DETAILS,
    entry: MockConfigEntry | None = None,
) -> tuple[MockConfigEntry, dict[str, AsyncMock]]:
    """Set up one loaded entry with the per-runnable detail feature configured."""
    if entry is None:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=WORKSPACE,
            data=ENTRY_DATA,
            options={
                **BASE_OPTIONS,
                OPT_RUNNABLE_DETAILS: True,
                OPT_RUNNABLES: [LIGHTS_SELECTION, NIGHT_SELECTION],
                **(options or {}),
            },
        )
        entry.add_to_hass(hass)
    with patched_client(
        capabilities=capabilities,
        runnable_jobs=runnable_jobs,
        jobs=jobs,
        details=details,
    ) as mocks:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, mocks


def _entity_id(hass: HomeAssistant, entry_id: str, domain: str, key: str, path: str) -> str:
    """Return the entity id of one per-runnable entity through the registry."""
    registry = er.async_get(hass)
    kind = "script" if path == LIGHTS_PATH else "flow"
    unique_id = f"{entry_id}_{key}_{kind}_{path}"
    entity_id = registry.async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None, f"missing entity for {unique_id}"
    return entity_id


def _state(hass: HomeAssistant, entry_id: str, domain: str, key: str, path: str) -> Any:
    """Return the state object of one per-runnable entity."""
    return hass.states.get(_entity_id(hass, entry_id, domain, key, path))


async def test_feature_off_creates_nothing_and_asks_windmill_for_nothing(
    hass: HomeAssistant,
) -> None:
    """Without the opt-in there is no coordinator, no entity and no extra request."""
    entry, mocks = await _setup_entry(hass, options={OPT_RUNNABLE_DETAILS: False})

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.runnable_run_coordinator is None
    mocks["runnable_jobs"].assert_not_awaited()
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert not [entity for entity in entities if "runnable_last" in entity.unique_id]


async def test_each_selected_runnable_becomes_its_own_device(hass: HomeAssistant) -> None:
    """Two selections produce two devices below the workspace and four entities each."""
    entry, _ = await _setup_entry(hass)

    devices = dr.async_get(hass)
    workspace = devices.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert workspace is not None
    for path, kind in ((LIGHTS_PATH, "script"), (NIGHT_PATH, "flow")):
        device = devices.async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_{kind}_{path}")})
        assert device is not None
        assert device.name == path
        assert device.via_device_id == workspace.id

    registry = er.async_get(hass)
    for domain, keys in LIGHTS_UNIQUE_IDS.items():
        for key in keys:
            for path in (LIGHTS_PATH, NIGHT_PATH):
                assert registry.async_get_entity_id(
                    domain,
                    DOMAIN,
                    f"{entry.entry_id}_{key}_{'script' if path == LIGHTS_PATH else 'flow'}_{path}",
                )


async def test_exact_read_answers_last_run_status_and_duration(hass: HomeAssistant) -> None:
    """The per-runnable read fills in a completion the shared window never carried."""
    entry, mocks = await _setup_entry(
        hass,
        runnable_jobs={
            LIGHTS_PATH: (
                _completed("a", LIGHTS_PATH, "script", JobState.SUCCESS, YESTERDAY, 2500),
            )
        },
    )

    assert mocks["runnable_jobs"].await_count == 2
    assert _state(hass, entry.entry_id, "sensor", "runnable_last_run", LIGHTS_PATH).state == (
        YESTERDAY.isoformat()
    )
    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_status", LIGHTS_PATH).state
        == "success"
    )
    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_duration", LIGHTS_PATH).state == "2.5"
    )
    assert (
        _state(hass, entry.entry_id, "binary_sensor", "runnable_running", LIGHTS_PATH).state
        == "off"
    )
    # An unobserved runnable reports nothing rather than a borrowed value.
    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_run", NIGHT_PATH).state == "unknown"
    )


async def test_a_runnable_reports_that_it_is_running(hass: HomeAssistant) -> None:
    """A running job of a selected runnable turns its binary sensor on."""
    entry, _ = await _setup_entry(
        hass, runnable_jobs={LIGHTS_PATH: (_running("b", LIGHTS_PATH, "script"),)}
    )

    assert (
        _state(hass, entry.entry_id, "binary_sensor", "runnable_running", LIGHTS_PATH).state == "on"
    )


async def test_shared_window_updates_details_without_starving_the_exact_read(
    hass: HomeAssistant,
) -> None:
    """The fast tier reports a completion at once and leaves the slow tier's schedule alone."""
    window: list[WindmillJob] = []

    async def jobs(page: Any) -> tuple[WindmillJob, ...]:
        return tuple(window)

    entry, mocks = await _setup_entry(
        hass, options={OPT_RUN_OBSERVATION: True}, runnable_jobs={}, jobs=jobs
    )
    assert mocks["runnable_jobs"].await_count == 2

    with patched_client(runnable_jobs={}, jobs=jobs) as later:
        window.append(_completed("c", LIGHTS_PATH, "script", JobState.FAILURE, TODAY, 800))
        async_fire_time_changed(hass, dt_util.utcnow() + RUN_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        # Seen through the shared window alone: no per-runnable request was needed for it.
        assert later["runnable_jobs"].await_count == 0
        assert (
            _state(hass, entry.entry_id, "sensor", "runnable_last_status", LIGHTS_PATH).state
            == "failure"
        )

        # The exact read must still fire on its own interval; a fast update that rescheduled
        # the coordinator would push it past this point forever.
        async_fire_time_changed(hass, dt_util.utcnow() + RUNNABLE_RUN_UPDATE_INTERVAL)
        await hass.async_block_till_done()
        assert later["runnable_jobs"].await_count == 2


async def test_an_older_completion_never_moves_the_last_run_backwards(
    hass: HomeAssistant,
) -> None:
    """A slow read answering with a stale window does not undo what the fast tier saw."""
    window = [_completed("d", LIGHTS_PATH, "script", JobState.SUCCESS, TODAY, 400)]

    async def jobs(page: Any) -> tuple[WindmillJob, ...]:
        return tuple(window)

    entry, _ = await _setup_entry(
        hass,
        options={OPT_RUN_OBSERVATION: True},
        runnable_jobs={
            LIGHTS_PATH: (_completed("e", LIGHTS_PATH, "script", JobState.FAILURE, YESTERDAY, 100),)
        },
        jobs=jobs,
    )

    assert _state(hass, entry.entry_id, "sensor", "runnable_last_run", LIGHTS_PATH).state == (
        TODAY.isoformat()
    )
    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_status", LIGHTS_PATH).state
        == "success"
    )


async def test_a_foreign_job_never_lands_on_a_runnable(hass: HomeAssistant) -> None:
    """Only jobs whose kind and path match a selection are folded into its state."""
    window = [
        _completed("f", "u/other/script", "script", JobState.SUCCESS, TODAY),
        # Same path, different kind: a flow job must not answer for the script selection.
        _completed("g", LIGHTS_PATH, "flow", JobState.SUCCESS, TODAY),
    ]

    async def jobs(page: Any) -> tuple[WindmillJob, ...]:
        return tuple(window)

    entry, _ = await _setup_entry(
        hass, options={OPT_RUN_OBSERVATION: True}, runnable_jobs={}, jobs=jobs
    )

    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_run", LIGHTS_PATH).state == "unknown"
    )


async def test_last_known_values_survive_a_reload(hass: HomeAssistant) -> None:
    """A restart restores the last completion but never claims a run is still running."""
    entry, _ = await _setup_entry(
        hass,
        runnable_jobs={
            LIGHTS_PATH: (
                _completed("h", LIGHTS_PATH, "script", JobState.CANCELED, YESTERDAY, 900),
                _running("i", LIGHTS_PATH, "script"),
            )
        },
    )
    assert (
        _state(hass, entry.entry_id, "binary_sensor", "runnable_running", LIGHTS_PATH).state == "on"
    )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # Windmill answers nothing this time: everything visible now comes from the store.
    await _setup_entry(hass, runnable_jobs={}, entry=entry)

    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_status", LIGHTS_PATH).state
        == "canceled"
    )
    assert _state(hass, entry.entry_id, "sensor", "runnable_last_run", LIGHTS_PATH).state == (
        YESTERDAY.isoformat()
    )
    assert (
        _state(hass, entry.entry_id, "binary_sensor", "runnable_running", LIGHTS_PATH).state
        == "off"
    )


async def test_deselecting_a_runnable_drops_its_entities_and_its_record(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A runnable that is no longer selected keeps neither entities nor stored state."""
    entry, _ = await _setup_entry(
        hass,
        runnable_jobs={
            LIGHTS_PATH: (_completed("j", LIGHTS_PATH, "script", JobState.SUCCESS, YESTERDAY),)
        },
    )
    stored = hass_storage[f"{DOMAIN}.runnable_runs.{entry.entry_id}"]["data"]["runnables"]
    assert f"script:{LIGHTS_PATH}" in stored

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, OPT_RUNNABLES: [NIGHT_SELECTION]}
    )
    await hass.async_block_till_done()
    with patched_client(runnable_jobs={}):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.u_automation_lights_last_run") is None
    assert hass.states.get("sensor.f_home_night_last_run") is not None
    stored = hass_storage[f"{DOMAIN}.runnable_runs.{entry.entry_id}"]["data"]["runnables"]
    assert list(stored) == [f"flow:{NIGHT_PATH}"]


async def test_a_missing_runnable_makes_its_entities_unavailable(hass: HomeAssistant) -> None:
    """A selection that no longer resolves reports unavailable instead of a stale value."""
    entry, _ = await _setup_entry(
        hass,
        details=WindmillNotFoundError("gone"),
        runnable_jobs={
            LIGHTS_PATH: (_completed("k", LIGHTS_PATH, "script", JobState.SUCCESS, YESTERDAY),)
        },
    )

    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_run", LIGHTS_PATH).state
        == "unavailable"
    )


async def test_a_rate_limited_detail_refresh_slows_down_instead_of_failing(
    hass: HomeAssistant,
) -> None:
    """A 429 stretches the detail interval and leaves the entry loaded."""
    entry, _ = await _setup_entry(hass, runnable_jobs={})
    coordinator = entry.runtime_data.runnable_run_coordinator
    assert coordinator is not None
    assert coordinator.update_interval == RUNNABLE_RUN_UPDATE_INTERVAL

    with patch(
        "custom_components.windmill.api.WindmillClient.async_list_runnable_jobs",
        side_effect=WindmillRateLimitError(retry_after=600.0),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + RUNNABLE_RUN_UPDATE_INTERVAL)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.update_interval == timedelta(seconds=600)


async def test_detail_state_carries_no_windmill_payload(hass: HomeAssistant) -> None:
    """The exposed attributes stay bounded metadata; no job identity or payload leaks."""
    entry, _ = await _setup_entry(
        hass,
        runnable_jobs={
            LIGHTS_PATH: (_completed("l", LIGHTS_PATH, "script", JobState.SUCCESS, YESTERDAY),)
        },
    )

    for domain, keys in LIGHTS_UNIQUE_IDS.items():
        for key in keys:
            state = _state(hass, entry.entry_id, domain, key, LIGHTS_PATH)
            assert "l" not in state.attributes.values()
            assert not {"job_id", "args", "result", "email", "worker"} & set(state.attributes)


async def test_details_survive_a_workspace_that_cannot_be_discovered(
    hass: HomeAssistant,
) -> None:
    """Without discovery there is no resolution to consult, so entities stay available."""
    entry, _ = await _setup_entry(
        hass,
        capabilities=_capabilities(script_discovery=UNSUPPORTED, flow_discovery=UNSUPPORTED),
        runnable_jobs={
            LIGHTS_PATH: (_completed("m", LIGHTS_PATH, "script", JobState.SUCCESS, YESTERDAY),)
        },
    )

    assert entry.runtime_data.runnable_coordinator is None
    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_status", LIGHTS_PATH).state
        == "success"
    )


async def test_a_degraded_capability_never_deletes_a_runnable_device(
    hass: HomeAssistant,
) -> None:
    """A Windmill hiccup at setup must not destroy registry entries.

    Entity existence follows configuration, not volatile Windmill state (ADR-0002). Pruning on
    a missing coordinator conflated "the user deselected this" with "the runs probe answered
    503 during this restart", and the second case would have taken the device, its entities,
    their entity ids, names, areas and history with it.
    """
    entry, _ = await _setup_entry(hass)
    devices = dr.async_get(hass)
    identifiers = {(DOMAIN, f"{entry.entry_id}_script_{LIGHTS_PATH}")}
    assert devices.async_get_device(identifiers=identifiers) is not None
    before = _entity_id(hass, entry.entry_id, "sensor", "runnable_last_run", LIGHTS_PATH)

    with patched_client(capabilities=_capabilities(runs=TEMPORARILY_UNAVAILABLE)):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.runtime_data.runnable_run_coordinator is None
    assert devices.async_get_device(identifiers=identifiers) is not None
    assert _entity_id(hass, entry.entry_id, "sensor", "runnable_last_run", LIGHTS_PATH) == before

    with patched_client(runnable_jobs={}):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert _state(hass, entry.entry_id, "sensor", "runnable_last_run", LIGHTS_PATH) is not None


async def test_turning_the_feature_off_drops_the_runnable_devices(hass: HomeAssistant) -> None:
    """Disabling the option is a configuration change, so its devices do go."""
    entry, _ = await _setup_entry(hass)
    devices = dr.async_get(hass)
    identifiers = {(DOMAIN, f"{entry.entry_id}_script_{LIGHTS_PATH}")}
    assert devices.async_get_device(identifiers=identifiers) is not None

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, OPT_RUNNABLE_DETAILS: False}
    )
    await hass.async_block_till_done()
    with patched_client():
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert devices.async_get_device(identifiers=identifiers) is None
    assert devices.async_get_device(identifiers={(DOMAIN, entry.entry_id)}) is not None


async def test_a_rejected_token_asks_for_reauthentication(hass: HomeAssistant) -> None:
    """An authentication failure of the detail read starts reauth instead of failing silently."""
    entry, _ = await _setup_entry(hass, runnable_jobs=WindmillAuthenticationError("rejected"))

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert [flow for flow in hass.config_entries.flow.async_progress() if flow["handler"] == DOMAIN]


async def test_a_pathless_job_is_ignored_by_the_fast_tier(hass: HomeAssistant) -> None:
    """A job without a runnable path belongs to no selection and is skipped."""
    window = [
        WindmillJob(
            id="n",
            state=JobState.SUCCESS,
            kind="preview",
            path=None,
            created_at=TODAY,
            completed_at=TODAY,
            duration_ms=10,
        )
    ]

    async def jobs(page: Any) -> tuple[WindmillJob, ...]:
        return tuple(window)

    entry, _ = await _setup_entry(
        hass, options={OPT_RUN_OBSERVATION: True}, runnable_jobs={}, jobs=jobs
    )

    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_run", LIGHTS_PATH).state == "unknown"
    )


def test_unreadable_stored_state_is_discarded() -> None:
    """Storage that no longer parses degrades to an empty state instead of raising."""
    assert load_runnable_run_states("not a mapping") == {}
    assert load_runnable_run_states({"runnables": "not a mapping"}) == {}
    # A key without the kind separator cannot identify a selection.
    assert load_runnable_run_states({"runnables": {"orphan": {}}}) == {}

    restored = load_runnable_run_states(
        {
            "runnables": {
                f"script:{LIGHTS_PATH}": {
                    "last_run": "2026-08-03T22:15:00+00:00",
                    "last_state": "no-such-state",
                    "last_duration_ms": "not a number",
                },
                f"flow:{NIGHT_PATH}": "not a mapping",
            }
        }
    )

    assert restored[("script", LIGHTS_PATH)].last_run == YESTERDAY
    assert restored[("script", LIGHTS_PATH)].last_state is None
    assert restored[("script", LIGHTS_PATH)].last_duration_ms is None
    assert restored[("flow", NIGHT_PATH)] == RunnableRunState()

    # A parsable state that is not a completion would reach an enum sensor whose options are
    # exactly the three terminal states, so it is discarded like an unparsable one.
    running = load_runnable_run_states(
        {"runnables": {f"script:{LIGHTS_PATH}": {"last_state": JobState.RUNNING.value}}}
    )
    assert running[("script", LIGHTS_PATH)].last_state is None


def _in(delta: timedelta) -> datetime:
    """Return a whole-second timestamp relative to now; states carry no microseconds."""
    return dt_util.utcnow().replace(microsecond=0) + delta


def _scheduled(job_id: str, path: str, kind: str, scheduled_for: datetime) -> WindmillJob:
    """Build one queued job that Windmill reserved for a future point in time."""
    return WindmillJob(
        id=job_id,
        state=JobState.QUEUED,
        kind=kind,
        path=path,
        created_at=TODAY,
        completed_at=None,
        duration_ms=None,
        scheduled_for=scheduled_for,
    )


async def test_a_scheduled_runnable_reports_its_next_run(hass: HomeAssistant) -> None:
    """The queued job Windmill reserved for a schedule is the next run."""
    due = _in(timedelta(hours=2))
    entry, _ = await _setup_entry(
        hass, runnable_jobs={LIGHTS_PATH: (_scheduled("o", LIGHTS_PATH, "script", due),)}
    )

    assert _state(hass, entry.entry_id, "sensor", "runnable_next_run", LIGHTS_PATH).state == (
        due.isoformat()
    )


async def test_an_unscheduled_runnable_reports_no_next_run(hass: HomeAssistant) -> None:
    """A runnable without a schedule reports nothing while its history keeps working."""
    entry, _ = await _setup_entry(
        hass,
        runnable_jobs={
            LIGHTS_PATH: (_completed("p", LIGHTS_PATH, "script", JobState.SUCCESS, YESTERDAY),)
        },
    )

    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_next_run", LIGHTS_PATH).state == "unknown"
    )
    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_status", LIGHTS_PATH).state
        == "success"
    )


async def test_the_earliest_of_several_reservations_wins(hass: HomeAssistant) -> None:
    """Where more than one slot is pending, the nearest one is the next run."""
    soon = _in(timedelta(minutes=30))
    later = _in(timedelta(hours=6))
    entry, _ = await _setup_entry(
        hass,
        runnable_jobs={
            LIGHTS_PATH: (
                _scheduled("q", LIGHTS_PATH, "script", later),
                _scheduled("r", LIGHTS_PATH, "script", soon),
            )
        },
    )

    assert _state(hass, entry.entry_id, "sensor", "runnable_next_run", LIGHTS_PATH).state == (
        soon.isoformat()
    )


async def test_a_job_waiting_for_a_worker_is_not_a_next_run(hass: HomeAssistant) -> None:
    """A queued job whose slot has passed is backlog, not a future run."""
    overdue = _in(-timedelta(minutes=5))
    entry, _ = await _setup_entry(
        hass,
        runnable_jobs={
            LIGHTS_PATH: (
                _scheduled("s", LIGHTS_PATH, "script", overdue),
                # A running job carries the slot it was started for, also in the past.
                _running("t", LIGHTS_PATH, "script"),
            )
        },
    )

    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_next_run", LIGHTS_PATH).state == "unknown"
    )


async def test_a_disabled_schedule_clears_the_next_run(hass: HomeAssistant) -> None:
    """Windmill deletes the reserved job when a schedule is disabled, and the sensor follows."""
    due = _in(timedelta(hours=1))
    reserved: dict[str, tuple[WindmillJob, ...]] = {
        LIGHTS_PATH: (_scheduled("u", LIGHTS_PATH, "script", due),)
    }
    entry, _ = await _setup_entry(hass, runnable_jobs=reserved)
    assert _state(hass, entry.entry_id, "sensor", "runnable_next_run", LIGHTS_PATH).state == (
        due.isoformat()
    )

    # The schedule is turned off in Windmill: `clear_schedule` removes the pending row.
    with patched_client(runnable_jobs={}):
        async_fire_time_changed(hass, dt_util.utcnow() + RUNNABLE_RUN_UPDATE_INTERVAL)
        await hass.async_block_till_done()

    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_next_run", LIGHTS_PATH).state == "unknown"
    )


async def test_a_restart_never_announces_a_stale_next_run(hass: HomeAssistant) -> None:
    """The reserved slot is not persisted: it may be gone by the time Home Assistant returns."""
    due = _in(timedelta(hours=3))
    entry, _ = await _setup_entry(
        hass,
        runnable_jobs={
            LIGHTS_PATH: (
                _scheduled("v", LIGHTS_PATH, "script", due),
                _completed("w", LIGHTS_PATH, "script", JobState.SUCCESS, YESTERDAY),
            )
        },
    )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await _setup_entry(hass, runnable_jobs={}, entry=entry)

    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_next_run", LIGHTS_PATH).state == "unknown"
    )
    # The history did survive; only the volatile half was dropped.
    assert (
        _state(hass, entry.entry_id, "sensor", "runnable_last_status", LIGHTS_PATH).state
        == "success"
    )
