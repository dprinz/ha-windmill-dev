"""Tests for bounded Windmill run observability."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.windmill.api import (
    JobState,
    WindmillAuthenticationError,
    WindmillJob,
    WindmillRateLimitError,
)
from custom_components.windmill.const import (
    DOMAIN,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
)
from custom_components.windmill.coordinator import (
    MAX_RUN_PAGES,
    RUN_PAGE_SIZE,
    RunObservationState,
)
from tests.test_health import CONNECTION, ENTRY_DATA, WORKSPACE, _capabilities

UNAUTHORIZED_RUNS = _capabilities()
BASE_TIME = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)
RUN_OPTIONS = {OPT_INSTANCE_HEALTH: False, OPT_RUN_OBSERVATION: True}


def _job(
    suffix: int,
    state: JobState,
    *,
    completed_minutes: int | None = None,
    path: str | None = "u/automation/lights",
) -> WindmillJob:
    """Build one bounded job projection for the tests."""
    completed_at = (
        None if completed_minutes is None else BASE_TIME + timedelta(minutes=completed_minutes)
    )
    return WindmillJob(
        id=f"00000000-0000-4000-8000-{suffix:012d}",
        state=state,
        kind="script",
        path=path,
        created_at=BASE_TIME,
        completed_at=completed_at,
        duration_ms=1500 if completed_at else None,
    )


RUNNING_JOB = _job(1, JobState.RUNNING)
QUEUED_JOB = _job(2, JobState.QUEUED)
SUCCESS_JOB = _job(3, JobState.SUCCESS, completed_minutes=1)
FAILURE_JOB = _job(4, JobState.FAILURE, completed_minutes=2)
CANCELED_JOB = _job(5, JobState.CANCELED, completed_minutes=3)
INITIAL_JOBS = (RUNNING_JOB, QUEUED_JOB, SUCCESS_JOB, FAILURE_JOB)


def _as_mock(value: Any) -> AsyncMock:
    """Return an asynchronous mock returning or raising the supplied value."""
    if isinstance(value, Exception):
        return AsyncMock(side_effect=value)
    return AsyncMock(return_value=value)


@contextmanager
def patched_client(*, jobs: Any = INITIAL_JOBS) -> Iterator[dict[str, AsyncMock]]:
    """Patch every Windmill call a run-enabled config entry performs."""
    mocks = {
        "connect": _as_mock(CONNECTION),
        "capabilities": _as_mock(_capabilities()),
        "jobs": _as_mock(jobs) if not callable(jobs) else AsyncMock(side_effect=jobs),
    }
    targets = {
        "connect": "custom_components.windmill.api.WindmillClient.async_connect",
        "capabilities": (
            "custom_components.windmill.api.WindmillClient.async_discover_capabilities"
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
    jobs: Any = INITIAL_JOBS,
    options: dict[str, bool] | None = None,
) -> MockConfigEntry:
    """Set up one loaded Windmill entry with run observation enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=WORKSPACE,
        data=ENTRY_DATA,
        options=options if options is not None else RUN_OPTIONS,
    )
    entry.add_to_hass(hass)
    with patched_client(jobs=jobs):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def _refresh(hass: HomeAssistant, *, jobs: Any, minutes: int = 2) -> None:
    """Advance time so the run coordinator refreshes once."""
    with patched_client(jobs=jobs):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=minutes))
        await hass.async_block_till_done()


async def test_run_entities_are_aggregates_only(hass: HomeAssistant) -> None:
    """Run observation adds four aggregates and one event entity, never one per job."""
    entry = await _setup_entry(hass)
    entity_registry = er.async_get(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.home_assistant_running_jobs_workspace").state == "1"
    assert hass.states.get("sensor.home_assistant_queued_jobs_workspace").state == "1"
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 5
    assert not any(SUCCESS_JOB.id in registered.unique_id for registered in entities)


async def test_last_run_timestamps_follow_completions(hass: HomeAssistant) -> None:
    """The last-success and last-failure sensors report observed completions."""
    await _setup_entry(hass)

    success = hass.states.get("sensor.home_assistant_last_successful_run")
    failure = hass.states.get("sensor.home_assistant_last_failed_run")
    assert success.state == (BASE_TIME + timedelta(minutes=1)).isoformat()
    assert failure.state == (BASE_TIME + timedelta(minutes=2)).isoformat()


async def test_first_observation_does_not_replay_history(hass: HomeAssistant) -> None:
    """The initial poll records the watermark without firing historical events."""
    await _setup_entry(hass)

    assert hass.states.get("event.home_assistant_run").state == STATE_UNKNOWN


async def test_new_completions_fire_one_event_each(hass: HomeAssistant) -> None:
    """A completion observed after the first poll fires exactly one bounded event."""
    await _setup_entry(hass)

    await _refresh(hass, jobs=(*INITIAL_JOBS, CANCELED_JOB))

    event = hass.states.get("event.home_assistant_run")
    assert event.attributes["event_type"] == "canceled"
    assert event.attributes["job_id"] == CANCELED_JOB.id
    assert event.attributes["path"] == "u/automation/lights"
    assert event.attributes["duration_ms"] == 1500
    fired_at = event.state

    await _refresh(hass, jobs=(*INITIAL_JOBS, CANCELED_JOB), minutes=4)

    assert hass.states.get("event.home_assistant_run").state == fired_at


async def test_duplicate_events_are_prevented_across_reloads(hass: HomeAssistant) -> None:
    """Retention state survives a reload, so a known completion never fires twice."""
    entry = await _setup_entry(hass)
    await _refresh(hass, jobs=(*INITIAL_JOBS, CANCELED_JOB))
    fired_at = hass.states.get("event.home_assistant_run").state
    assert hass.states.get("event.home_assistant_run").attributes["event_type"] == "canceled"

    with patched_client(jobs=(*INITIAL_JOBS, CANCELED_JOB)):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    await _refresh(hass, jobs=(*INITIAL_JOBS, CANCELED_JOB), minutes=6)

    # The entity restores its last event; an identical timestamp proves nothing fired again.
    assert hass.states.get("event.home_assistant_run").state == fired_at
    assert (
        hass.states.get("sensor.home_assistant_last_failed_run").state
        == (BASE_TIME + timedelta(minutes=2)).isoformat()
    )


async def test_last_success_never_moves_backwards(hass: HomeAssistant) -> None:
    """A window without a successful job keeps the stored last-success timestamp."""
    await _setup_entry(hass)

    await _refresh(hass, jobs=(RUNNING_JOB,))

    assert (
        hass.states.get("sensor.home_assistant_last_successful_run").state
        == (BASE_TIME + timedelta(minutes=1)).isoformat()
    )
    assert hass.states.get("sensor.home_assistant_running_jobs_workspace").state == "1"
    assert hass.states.get("sensor.home_assistant_queued_jobs_workspace").state == "0"


async def test_completion_without_timestamp_never_fires(hass: HomeAssistant) -> None:
    """A completion without a completion timestamp cannot be deduplicated, so it is skipped."""
    await _setup_entry(hass)
    undated = WindmillJob(
        id="00000000-0000-4000-8000-000000000009",
        state=JobState.SUCCESS,
        kind="script",
        path=None,
        created_at=BASE_TIME,
        completed_at=None,
        duration_ms=None,
    )

    await _refresh(hass, jobs=(*INITIAL_JOBS, undated))

    assert hass.states.get("event.home_assistant_run").state == STATE_UNKNOWN


async def test_page_walk_is_bounded(hass: HomeAssistant) -> None:
    """A busy workspace is read through a bounded number of pages."""
    full_page = tuple(_job(index + 100, JobState.RUNNING) for index in range(RUN_PAGE_SIZE))
    await _setup_entry(hass, jobs=full_page)

    with patched_client(jobs=full_page) as mocks:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done()

    assert mocks["jobs"].await_count == MAX_RUN_PAGES
    assert hass.states.get("sensor.home_assistant_running_jobs_workspace").state == str(
        RUN_PAGE_SIZE * MAX_RUN_PAGES
    )


async def test_page_walk_stops_at_the_watermark(hass: HomeAssistant) -> None:
    """Pages that contain only known completions end the walk early."""
    full_page = tuple(
        _job(index + 200, JobState.SUCCESS, completed_minutes=1) for index in range(RUN_PAGE_SIZE)
    )
    await _setup_entry(hass, jobs=full_page)

    with patched_client(jobs=full_page) as mocks:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done()

    assert mocks["jobs"].await_count == 1


async def test_rate_limited_refresh_marks_entities_unavailable(hass: HomeAssistant) -> None:
    """Rate limiting degrades the run entities and recovers on the next refresh."""
    entry = await _setup_entry(hass)

    await _refresh(hass, jobs=WindmillRateLimitError(retry_after=30.0))

    assert entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("sensor.home_assistant_running_jobs_workspace").state == STATE_UNAVAILABLE
    )

    await _refresh(hass, jobs=INITIAL_JOBS, minutes=4)

    assert hass.states.get("sensor.home_assistant_running_jobs_workspace").state == "1"


async def test_run_authentication_failure_triggers_reauth(hass: HomeAssistant) -> None:
    """A revoked token during run polling starts the reauthentication flow."""
    await _setup_entry(hass)

    await _refresh(hass, jobs=WindmillAuthenticationError())

    flows = [
        flow for flow in hass.config_entries.flow.async_progress() if flow["handler"] == DOMAIN
    ]
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


@pytest.mark.parametrize(
    ("options", "capabilities"),
    [
        ({OPT_INSTANCE_HEALTH: False, OPT_RUN_OBSERVATION: False}, None),
        ({OPT_INSTANCE_HEALTH: False}, "unauthorized"),
    ],
)
async def test_disabled_or_unsupported_runs_create_no_entities(
    hass: HomeAssistant, options: dict[str, bool], capabilities: str | None
) -> None:
    """An opted-out or unsupported run feature loads the entry without run entities."""
    entry = MockConfigEntry(domain=DOMAIN, title=WORKSPACE, data=ENTRY_DATA, options=options)
    entry.add_to_hass(hass)
    matrix = _capabilities()
    if capabilities == "unauthorized":
        from custom_components.windmill.api import (
            CapabilityAvailability,
            CapabilityReason,
            CapabilityStatus,
        )

        matrix = _capabilities(
            runs=CapabilityAvailability(
                CapabilityStatus.UNAUTHORIZED, CapabilityReason.PERMISSION_DENIED
            )
        )

    with (
        patch(
            "custom_components.windmill.api.WindmillClient.async_connect",
            new=AsyncMock(return_value=CONNECTION),
        ),
        patch(
            "custom_components.windmill.api.WindmillClient.async_discover_capabilities",
            new=AsyncMock(return_value=matrix),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.home_assistant_running_jobs_workspace") is None
    assert hass.states.get("event.home_assistant_run") is None


def test_retention_state_rejects_old_and_corrupt_entries() -> None:
    """The retention model ignores stale completions and unreadable stored state."""
    state = RunObservationState.from_dict(
        {"watermark": "not-a-time", "seen": "not-a-list", "last_success": 42}
    )
    assert state.watermark is None
    assert not state.seen

    assert state.remember(SUCCESS_JOB) is True
    assert state.remember(SUCCESS_JOB) is False
    stale = _job(99, JobState.FAILURE, completed_minutes=-5)
    assert state.remember(stale) is False

    restored = RunObservationState.from_dict(state.as_dict())
    assert restored.watermark == state.watermark
    assert list(restored.seen) == list(state.seen)
    assert restored.last_success == state.last_success
    assert RunObservationState.from_dict({"watermark": "2026-08-02T10:00:00"}).watermark is None
