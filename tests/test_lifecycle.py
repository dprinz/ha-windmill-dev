"""Tests for the bounded registry of Home Assistant-started Windmill jobs."""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.windmill.api import (
    JobState,
    WindmillAuthorizationError,
    WindmillConflictError,
    WindmillConnectionError,
    WindmillJob,
    WindmillNotFoundError,
)
from custom_components.windmill.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_JOB_ID,
    DOMAIN,
    MAX_TRACKED_JOBS,
    OPT_RUN_OBSERVATION,
    OPT_RUNNABLES,
)
from custom_components.windmill.coordinator import StartedJobRegistry, TrackedJob
from tests.test_execution import JOB_ID, _run
from tests.test_runnables import LIGHTS_SELECTION, _setup_entry, patched_client

OTHER_JOB_ID = "00000000-0000-4000-8000-00000000000b"


async def _start_job(hass: HomeAssistant, entry: MockConfigEntry, job_id: str = JOB_ID) -> None:
    """Start one runnable so the job enters the local registry."""
    with patch(
        "custom_components.windmill.api.WindmillClient.async_run_runnable",
        new=AsyncMock(return_value=job_id),
    ):
        await _run(hass, entry)


async def _cancel(hass: HomeAssistant, entry: MockConfigEntry, job_id: str = JOB_ID) -> None:
    """Call the cancel action for one job identifier."""
    await hass.services.async_call(
        DOMAIN,
        "cancel",
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id, ATTR_JOB_ID: job_id},
        blocking=True,
    )


async def test_only_started_jobs_are_tracked_and_cancellable(hass: HomeAssistant) -> None:
    """A job Home Assistant did not start is never cancellable through the integration."""
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]})

    with (
        patch(
            "custom_components.windmill.api.WindmillClient.async_cancel_job",
            new=AsyncMock(),
        ) as cancel,
        pytest.raises(ServiceValidationError) as caught,
    ):
        await _cancel(hass, entry, OTHER_JOB_ID)

    assert caught.value.translation_key == "job_not_tracked"
    cancel.assert_not_awaited()

    await _start_job(hass, entry)
    with patch(
        "custom_components.windmill.api.WindmillClient.async_cancel_job", new=AsyncMock()
    ) as cancel:
        await _cancel(hass, entry)

    assert cancel.await_args.args[0] == JOB_ID
    assert entry.runtime_data.started_jobs.get(JOB_ID) is None


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (WindmillNotFoundError(), ServiceValidationError),
        (WindmillConflictError(), ServiceValidationError),
        (WindmillAuthorizationError(), HomeAssistantError),
        (WindmillConnectionError(), HomeAssistantError),
    ],
)
async def test_cancellation_failures_are_predictable(
    hass: HomeAssistant, error: Exception, expected: type[Exception]
) -> None:
    """Completed, missing, unauthorized and unreachable cancellations stay distinct."""
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]})
    await _start_job(hass, entry)

    with (
        patch(
            "custom_components.windmill.api.WindmillClient.async_cancel_job",
            new=AsyncMock(side_effect=error),
        ),
        pytest.raises(expected),
    ):
        await _cancel(hass, entry)

    forgotten = isinstance(error, WindmillNotFoundError | WindmillConflictError)
    assert (entry.runtime_data.started_jobs.get(JOB_ID) is None) is forgotten


async def test_registry_survives_reload_without_duplicate_events(hass: HomeAssistant) -> None:
    """Tracking survives a reload and a completion is still reported exactly once."""
    with patch(
        "custom_components.windmill.api.WindmillClient.async_list_jobs",
        new=AsyncMock(return_value=()),
    ):
        entry = await _setup_entry(
            hass,
            options={OPT_RUNNABLES: [LIGHTS_SELECTION], OPT_RUN_OBSERVATION: True},
        )
        await _start_job(hass, entry)

        with patched_client():
            await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()

    tracked = entry.runtime_data.started_jobs.get(JOB_ID)
    assert tracked is not None
    assert tracked.path == "u/automation/lights"

    completion = WindmillJob(
        id=JOB_ID,
        state=JobState.SUCCESS,
        kind="script",
        path="u/automation/lights",
        created_at=dt_util.utcnow(),
        completed_at=dt_util.utcnow(),
        duration_ms=1200,
    )
    with (
        patched_client(),
        patch(
            "custom_components.windmill.api.WindmillClient.async_list_jobs",
            new=AsyncMock(return_value=(completion,)),
        ),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done()
        first = hass.states.get("event.home_assistant_run")
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=4))
        await hass.async_block_till_done()

    assert first.attributes["started_by_home_assistant"] is True
    assert first.attributes["job_id"] == JOB_ID
    assert hass.states.get("event.home_assistant_run").state == first.state
    assert entry.runtime_data.started_jobs.get(JOB_ID) is None


async def test_registry_is_bounded_by_size_and_age() -> None:
    """The registry keeps at most the documented number and age of jobs."""
    saved: list[Any] = []

    class _Store:
        async def async_load(self) -> Any:
            return {
                "jobs": [
                    {
                        "job_id": "expired",
                        "kind": "script",
                        "path": "u/a/b",
                        "started_at": (dt_util.utcnow() - timedelta(hours=25)).isoformat(),
                    },
                    {"job_id": "broken"},
                    "not-a-job",
                ]
            }

        async def async_save(self, data: Any) -> None:
            saved.append(data)

    registry = StartedJobRegistry(_Store())  # type: ignore[arg-type]
    await registry.async_load()
    assert registry.tracked == ()

    for index in range(MAX_TRACKED_JOBS + 5):
        await registry.async_track(
            TrackedJob(
                job_id=f"job-{index}",
                kind="script",
                path="u/a/b",
                started_at=datetime(2026, 8, 2, 10, 0, tzinfo=UTC) + timedelta(seconds=index),
            )
        )

    assert len(registry.tracked) == MAX_TRACKED_JOBS
    assert registry.get("job-0") is None
    assert registry.get(f"job-{MAX_TRACKED_JOBS + 4}") is not None
    assert all(len(entry["jobs"]) <= MAX_TRACKED_JOBS for entry in saved)


async def test_registry_stores_no_payloads(hass: HomeAssistant) -> None:
    """The registry keeps identifiers and metadata only."""
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]})
    await _start_job(hass, entry)

    tracked = entry.runtime_data.started_jobs.get(JOB_ID)
    assert set(tracked.as_dict()) == {"job_id", "kind", "path", "started_at"}
    assert "kitchen" not in str(tracked.as_dict())
