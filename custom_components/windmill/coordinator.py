"""Home Assistant coordinators for shared Windmill runtime data."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    AddressingMode,
    CapabilityMatrix,
    JobState,
    PageRequest,
    RunnableDetails,
    RunnableKind,
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillClient,
    WindmillDetailedHealth,
    WindmillError,
    WindmillHealthStatus,
    WindmillJob,
    WindmillNotFoundError,
    WindmillRateLimitError,
    WindmillRequestError,
    WindmillRunnable,
    WindmillUpdateStatus,
    WindmillWorker,
    normalize_runnable_path,
)
from .const import (
    DEFAULT_RATE_LIMIT_BACKOFF_SECONDS,
    DEFAULT_RUN_SCOPE,
    DOMAIN,
    MAX_RATE_LIMIT_BACKOFF_SECONDS,
    MAX_SELECTED_RUNNABLES,
    MAX_TRACKED_JOBS,
    OPT_RUN_SCOPE,
    RUN_SCOPE_SELECTED,
    RUN_SCOPE_STARTED,
    RUN_SCOPES,
    TRACKED_JOB_TTL_HOURS,
)

_LOGGER = logging.getLogger(__name__)
CAPABILITY_UPDATE_INTERVAL = timedelta(hours=6)
HEALTH_UPDATE_INTERVAL = timedelta(seconds=60)
WORKER_UPDATE_INTERVAL = timedelta(minutes=2)
WORKER_PAGE_SIZE = 100
MAX_WORKER_PAGES = 5
RUN_UPDATE_INTERVAL = timedelta(seconds=60)
# One `jobs/list` page carries the requested completed rows plus the entire queue, and the
# transport rejects a response above MAX_RESPONSE_BYTES. A modest page keeps a full window
# plus a plausible queue well inside that cap.
RUN_PAGE_SIZE = 30
MAX_RUN_PAGES = 3
MAX_SEEN_JOBS = 200
RUN_STORAGE_VERSION = 1
JOB_STORAGE_VERSION = 1
RUNNABLE_RUN_STORAGE_VERSION = 1
RUNNABLE_UPDATE_INTERVAL = timedelta(minutes=30)
# One exact read per selected runnable, so the interval is deliberately slower than the shared
# window: that window already delivers a completion within the minute it is observed.
RUNNABLE_RUN_UPDATE_INTERVAL = timedelta(minutes=5)
# The queued half of the response is scoped to a single path, so a small page is enough: only
# the completions are bounded by it, and one completion is all a "last run" needs.
RUNNABLE_RUN_PAGE_SIZE = 5
RUNNABLE_PAGE_SIZE = 100
MAX_RUNNABLE_PAGES = 3
UPDATE_CHECK_INTERVAL = timedelta(hours=6)


def async_run_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Return the run-observation store of one config entry."""
    return Store(hass, RUN_STORAGE_VERSION, f"{DOMAIN}.runs.{entry_id}")


def async_job_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Return the started-job store of one config entry."""
    return Store(hass, JOB_STORAGE_VERSION, f"{DOMAIN}.jobs.{entry_id}")


def async_runnable_run_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Return the per-runnable run-detail store of one config entry."""
    return Store(hass, RUNNABLE_RUN_STORAGE_VERSION, f"{DOMAIN}.runnable_runs.{entry_id}")


# Every per-entry store is built through this tuple, so entry removal cannot forget one.
ENTRY_STORES: tuple[Callable[[HomeAssistant, str], Store[dict[str, Any]]], ...] = (
    async_run_store,
    async_job_store,
    async_runnable_run_store,
)


class WindmillCoordinator[DataT](DataUpdateCoordinator[DataT]):
    """Shared polling behavior for every Windmill coordinator.

    Home Assistant already throttles the logging of repeated refresh failures: the first failure is
    logged at error level and every following one at debug level until a refresh succeeds. What it
    does not do is slow down. When Windmill answers with a rate limit, polling at the normal
    interval keeps producing requests the server has just refused, so the interval is stretched
    until one refresh succeeds again.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Remember the configured interval so backoff can be undone exactly."""
        super().__init__(*args, **kwargs)
        self._base_interval = self.update_interval

    async def _async_update_data(self) -> DataT:
        """Observe once, applying rate-limit backoff and restoring it on recovery."""
        try:
            data = await self._async_observe()
        except UpdateFailed as err:
            self._async_apply_backoff(err.__cause__)
            raise
        if self.update_interval != self._base_interval:
            self.update_interval = self._base_interval
        return data

    async def _async_observe(self) -> DataT:
        """Perform one observation; subclasses implement this instead of `_async_update_data`."""
        raise NotImplementedError

    @callback
    def _async_apply_backoff(self, cause: BaseException | None) -> None:
        """Stretch the interval only when Windmill itself asked for it."""
        if not isinstance(cause, WindmillRateLimitError):
            return
        requested = cause.retry_after or DEFAULT_RATE_LIMIT_BACKOFF_SECONDS
        base = 0.0 if self._base_interval is None else self._base_interval.total_seconds()
        # The cap applies to the requested backoff, never to the base interval: a coordinator
        # that already polls slower than the cap must not speed up after a 429.
        seconds = max(base, min(requested, MAX_RATE_LIMIT_BACKOFF_SECONDS))
        backoff = timedelta(seconds=seconds)
        if self.update_interval != backoff:
            _LOGGER.debug("Windmill rate limited %s; polling every %s", self.name, backoff)
            self.update_interval = backoff


@dataclass
class RunObservationState:
    """Bounded retention model that prevents replayed and duplicated run events."""

    watermark: datetime | None = None
    seen: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_SEEN_JOBS))
    last_success: datetime | None = None
    last_failure: datetime | None = None
    initialized: bool = False
    scope: str = DEFAULT_RUN_SCOPE

    def align_scope(self, scope: str) -> None:
        """Reset the scoped timestamps when the configured scope changed.

        The watermark, the seen identifiers and the initialization flag are kept on purpose:
        they are what stops a scope change from replaying historical completions as new
        events. Only the last-run timestamps are scoped per definition, so they restart.
        """
        if self.scope == scope:
            return
        self.scope = scope
        self.last_success = None
        self.last_failure = None

    def remember(self, job: WindmillJob) -> bool:
        """Record one completion and return whether it was newly observed."""
        completed_at = job.completed_at
        if completed_at is None or job.id in self.seen:
            return False
        if self.watermark is not None and completed_at < self.watermark:
            return False
        self.seen.append(job.id)
        self.watermark = (
            completed_at if self.watermark is None else max(self.watermark, completed_at)
        )
        if job.state is JobState.SUCCESS:
            self.last_success = self._advance(self.last_success, completed_at)
        elif job.state is JobState.FAILURE:
            self.last_failure = self._advance(self.last_failure, completed_at)
        return True

    def as_dict(self) -> dict[str, Any]:
        """Return the JSON-serializable retention state."""
        return {
            "watermark": _isoformat(self.watermark),
            "seen": list(self.seen),
            "last_success": _isoformat(self.last_success),
            "last_failure": _isoformat(self.last_failure),
            "initialized": self.initialized,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, data: Any) -> RunObservationState:
        """Restore retention state, discarding anything unreadable."""
        state = cls()
        if not isinstance(data, dict):
            return state
        state.watermark = _parse_stored_timestamp(data.get("watermark"))
        state.last_success = _parse_stored_timestamp(data.get("last_success"))
        state.last_failure = _parse_stored_timestamp(data.get("last_failure"))
        seen = data.get("seen")
        if isinstance(seen, list):
            state.seen.extend(str(job_id) for job_id in seen[-MAX_SEEN_JOBS:])
        state.initialized = data.get("initialized") is True
        scope = data.get("scope")
        if isinstance(scope, str) and scope in RUN_SCOPES:
            state.scope = scope
        return state

    @staticmethod
    def _advance(current: datetime | None, candidate: datetime) -> datetime:
        """Move a last-run timestamp forward only."""
        return candidate if current is None else max(current, candidate)


def _isoformat(value: datetime | None) -> str | None:
    """Return an ISO-8601 string for storage."""
    return None if value is None else value.isoformat()


def _parse_stored_timestamp(value: Any) -> datetime | None:
    """Parse a stored timestamp and ignore anything unreadable."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


@dataclass(frozen=True, slots=True)
class WindmillHealthSnapshot:
    """One immutable health observation shared by every health entity."""

    status: WindmillHealthStatus
    detailed: WindmillDetailedHealth | None


@dataclass(frozen=True, slots=True)
class WorkerGroupState:
    """Bounded aggregate of the alive workers of one worker group."""

    alive_workers: int = 0
    versions: int = 0


@dataclass(frozen=True, slots=True)
class WindmillWorkerSnapshot:
    """One immutable worker observation shared by every worker entity."""

    groups: Mapping[str, WorkerGroupState]
    instances: Mapping[str, int]


class WindmillCapabilityCoordinator(WindmillCoordinator[CapabilityMatrix]):
    """Share a bounded capability snapshot across later platforms."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        client: WindmillClient,
    ) -> None:
        """Initialize the config-entry-owned capability coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} capabilities",
            config_entry=entry,
            update_interval=CAPABILITY_UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_observe(self) -> CapabilityMatrix:
        """Refresh the safe read-only capability matrix."""
        try:
            return await self.client.async_discover_capabilities()
        except WindmillAuthenticationError as err:
            raise ConfigEntryAuthFailed("Windmill authentication failed") from err
        except WindmillError as err:
            raise UpdateFailed("Unable to refresh Windmill capabilities") from err


class WindmillHealthCoordinator(WindmillCoordinator[WindmillHealthSnapshot]):
    """Poll instance health once for every health entity of a config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        client: WindmillClient,
        *,
        detailed: bool,
    ) -> None:
        """Initialize the config-entry-owned health coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} health",
            config_entry=entry,
            update_interval=HEALTH_UPDATE_INTERVAL,
        )
        self.client = client
        self.detailed = detailed

    async def _async_observe(self) -> WindmillHealthSnapshot:
        """Refresh coarse health and, when enabled, the additive detailed health."""
        try:
            status = await self.client.async_get_health_status()
        except WindmillAuthenticationError as err:
            raise ConfigEntryAuthFailed("Windmill authentication failed") from err
        except WindmillError as err:
            raise UpdateFailed("Unable to refresh Windmill health") from err

        detailed: WindmillDetailedHealth | None = None
        if self.detailed:
            try:
                detailed = await self.client.async_get_detailed_health()
            except WindmillAuthenticationError as err:
                raise ConfigEntryAuthFailed("Windmill authentication failed") from err
            except WindmillError:
                # Detailed health is administrative and additive; coarse health still applies.
                _LOGGER.debug("Detailed Windmill health is currently unavailable")
        return WindmillHealthSnapshot(status=status, detailed=detailed)


class WindmillWorkerCoordinator(WindmillCoordinator[WindmillWorkerSnapshot]):
    """Poll a bounded worker listing once for every worker entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        client: WindmillClient,
        *,
        known_groups: tuple[str, ...],
    ) -> None:
        """Initialize the config-entry-owned worker coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} workers",
            config_entry=entry,
            update_interval=WORKER_UPDATE_INTERVAL,
        )
        self.client = client
        self.known_groups = known_groups

    async def _async_observe(self) -> WindmillWorkerSnapshot:
        """Walk a bounded number of worker pages and aggregate them safely."""
        workers: list[WindmillWorker] = []
        try:
            for page in range(1, MAX_WORKER_PAGES + 1):
                rows = await self.client.async_list_workers(
                    PageRequest(page=page, per_page=WORKER_PAGE_SIZE)
                )
                workers.extend(rows)
                if len(rows) < WORKER_PAGE_SIZE:
                    break
            else:
                _LOGGER.debug(
                    "Windmill reported more than %s alive workers; counts are a lower bound",
                    MAX_WORKER_PAGES * WORKER_PAGE_SIZE,
                )
        except WindmillAuthenticationError as err:
            raise ConfigEntryAuthFailed("Windmill authentication failed") from err
        except WindmillError as err:
            raise UpdateFailed("Unable to refresh Windmill workers") from err

        return self._aggregate(workers)

    def _aggregate(self, workers: list[WindmillWorker]) -> WindmillWorkerSnapshot:
        """Reduce worker rows to bounded per-group and per-instance counts."""
        counts: dict[str, int] = dict.fromkeys(self.known_groups, 0)
        versions: dict[str, set[str]] = {group: set() for group in self.known_groups}
        instances: dict[str, int] = {}
        for worker in workers:
            counts[worker.group] = counts.get(worker.group, 0) + 1
            versions.setdefault(worker.group, set()).add(worker.version)
            instances[worker.instance] = instances.get(worker.instance, 0) + 1
        groups = {
            group: WorkerGroupState(alive_workers=alive, versions=len(versions[group]))
            for group, alive in counts.items()
        }
        return WindmillWorkerSnapshot(groups=groups, instances=instances)


@dataclass(frozen=True, slots=True)
class WindmillRunEvent:
    """One newly observed completion that an event entity may publish."""

    job_id: str
    state: JobState
    kind: str
    path: str | None
    duration_ms: int | None


@dataclass(frozen=True, slots=True)
class WindmillRunSnapshot:
    """One immutable run observation shared by every run entity."""

    running: int
    queued: int
    last_success: datetime | None
    last_failure: datetime | None
    new_events: tuple[WindmillRunEvent, ...] = ()


def _is_reserved(job: WindmillJob) -> bool:
    """Return whether a job is a slot Windmill reserved for a future point in time."""
    return job.scheduled_for is not None and job.scheduled_for > dt_util.utcnow()


def run_scope_from_options(options: Mapping[str, Any]) -> str:
    """Return the configured run scope, falling back to the safe default."""
    scope = str(options.get(OPT_RUN_SCOPE, DEFAULT_RUN_SCOPE))
    return scope if scope in RUN_SCOPES else DEFAULT_RUN_SCOPE


class WindmillRunCoordinator(WindmillCoordinator[WindmillRunSnapshot]):
    """Observe bounded top-level run activity without one entity per job."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        client: WindmillClient,
        store: Store[dict[str, Any]],
        state: RunObservationState,
        *,
        scope: str,
        selected: frozenset[tuple[str, str]],
        started_jobs: StartedJobRegistry,
        job_sink: Callable[[tuple[WindmillJob, ...]], Awaitable[None]] | None = None,
    ) -> None:
        """Initialize the config-entry-owned run coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} runs",
            config_entry=entry,
            update_interval=RUN_UPDATE_INTERVAL,
        )
        self.client = client
        self._store = store
        self._state = state
        self._scope = scope
        self._selected = selected
        self._started_jobs = started_jobs
        # The observation scope is a retention decision for the aggregate sensors, not a filter
        # on what was seen, so the sink receives the whole deduplicated window.
        self._job_sink = job_sink

    async def _async_observe(self) -> WindmillRunSnapshot:
        """Walk bounded job pages, aggregate them and derive new completion events."""
        # Keyed by job id: upstream ignores the offset of `jobs/list`, so a later page can
        # repeat an earlier one. Counting a repeated job twice would inflate the aggregates.
        seen: dict[str, WindmillJob] = {}
        try:
            for page in range(1, MAX_RUN_PAGES + 1):
                rows = await self.client.async_list_jobs(
                    PageRequest(page=page, per_page=RUN_PAGE_SIZE)
                )
                for job in rows:
                    seen.setdefault(job.id, job)
                # `per_page` bounds only the completed half of the response, so a short page
                # is one with fewer completions than requested — the total row count says
                # nothing about whether another page exists.
                completed = sum(1 for job in rows if job.is_completed)
                if completed < RUN_PAGE_SIZE or self._reached_watermark(rows):
                    break
        except WindmillAuthenticationError as err:
            raise ConfigEntryAuthFailed("Windmill authentication failed") from err
        except WindmillError as err:
            raise UpdateFailed("Unable to refresh Windmill runs") from err

        observed = tuple(seen.values())
        snapshot = self._observe(list(observed))
        await self._store.async_save(self._state.as_dict())
        if self._job_sink is not None:
            await self._job_sink(observed)
        return snapshot

    def _reached_watermark(self, rows: tuple[WindmillJob, ...]) -> bool:
        """Return whether a page contains only completions at or below the watermark."""
        watermark = self._state.watermark
        if watermark is None:
            return False
        completions = [job.completed_at for job in rows if job.completed_at is not None]
        return bool(completions) and max(completions) <= watermark

    def _in_scope(self, job: WindmillJob) -> bool:
        """Return whether one parsed job belongs to the configured observation scope.

        Only the bounded job projection is consulted: the runnable key for a selection
        match and the job identifier for a started-by-Home-Assistant match.
        """
        if self._scope == RUN_SCOPE_SELECTED:
            return job.path is not None and (job.kind, job.path) in self._selected
        if self._scope == RUN_SCOPE_STARTED:
            return self._started_jobs.get(job.id) is not None
        return True

    def _observe(self, jobs: list[WindmillJob]) -> WindmillRunSnapshot:
        """Aggregate the scoped window and turn unseen completions into bounded events."""
        scoped = [job for job in jobs if self._in_scope(job)]
        running = sum(1 for job in scoped if job.state is JobState.RUNNING)
        # A reserved slot is a queued job too: Windmill writes the next occurrence of every
        # enabled schedule into the queue as soon as the previous one finishes. Counting those
        # would make the queue depth of an idle workspace equal its number of schedules, and it
        # would never reach zero. Only work that is actually waiting for a worker is counted.
        queued = sum(1 for job in scoped if job.state is JobState.QUEUED and not _is_reserved(job))
        completions = [
            (job.completed_at, job.id, job)
            for job in scoped
            if job.is_completed and job.completed_at is not None
        ]
        completions.sort(key=lambda entry: (entry[0], entry[1]))

        first_observation = not self._state.initialized
        events: list[WindmillRunEvent] = []
        for _, _, job in completions:
            if self._state.remember(job) and not first_observation:
                events.append(
                    WindmillRunEvent(
                        job_id=job.id,
                        state=job.state,
                        kind=job.kind,
                        path=job.path,
                        duration_ms=job.duration_ms,
                    )
                )
        self._state.initialized = True
        return WindmillRunSnapshot(
            running=running,
            queued=queued,
            last_success=self._state.last_success,
            last_failure=self._state.last_failure,
            new_events=tuple(events),
        )


@dataclass(frozen=True, slots=True)
class RunnableSelection:
    """One explicitly selected runnable as stored in config-entry options."""

    kind: RunnableKind
    path: str
    mode: AddressingMode

    @classmethod
    def from_dict(cls, data: Any) -> RunnableSelection | None:
        """Restore one stored selection, ignoring anything unreadable."""
        if not isinstance(data, dict):
            return None
        try:
            kind = RunnableKind(str(data.get("kind")))
            mode = AddressingMode(str(data.get("mode", AddressingMode.LATEST.value)))
            path = normalize_runnable_path(str(data.get("path", "")))
        except ValueError, WindmillRequestError:
            return None
        return cls(kind=kind, path=path, mode=mode)

    def as_dict(self) -> dict[str, str]:
        """Return the JSON-serializable selection."""
        return {"kind": self.kind.value, "path": self.path, "mode": self.mode.value}

    @property
    def key(self) -> tuple[str, str]:
        """Return the stable identity of this selection."""
        return (self.kind.value, self.path)


@dataclass(frozen=True, slots=True)
class ResolvedRunnable:
    """One selected runnable resolved against the current workspace."""

    selection: RunnableSelection
    available: bool
    reason: str | None = None
    details: RunnableDetails | None = None

    @property
    def executable(self) -> bool:
        """Return whether a later execution ticket may address this runnable."""
        return self.available and self.details is not None and self.details.schema_supported


def load_selections(raw: Any) -> tuple[RunnableSelection, ...]:
    """Read the stored runnable selection, discarding unreadable entries."""
    if not isinstance(raw, list):
        return ()
    selections: list[RunnableSelection] = []
    seen: set[tuple[str, str]] = set()
    for item in raw[:MAX_SELECTED_RUNNABLES]:
        selection = RunnableSelection.from_dict(item)
        if selection is None or selection.key in seen:
            continue
        seen.add(selection.key)
        selections.append(selection)
    return tuple(selections)


class WindmillRunnableCoordinator(WindmillCoordinator[Mapping[tuple[str, str], ResolvedRunnable]]):
    """Resolve explicitly selected runnables without exposing a whole workspace."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        client: WindmillClient,
        selections: tuple[RunnableSelection, ...],
    ) -> None:
        """Initialize the config-entry-owned runnable coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} runnables",
            config_entry=entry,
            update_interval=RUNNABLE_UPDATE_INTERVAL,
        )
        self.client = client
        self.selections = selections

    async def _async_observe(self) -> Mapping[tuple[str, str], ResolvedRunnable]:
        """Resolve every selection into availability and bounded schema metadata."""
        resolved: dict[tuple[str, str], ResolvedRunnable] = {}
        for selection in self.selections:
            try:
                details = await self.client.async_get_runnable(selection.kind, selection.path)
            except WindmillAuthenticationError as err:
                raise ConfigEntryAuthFailed("Windmill authentication failed") from err
            except WindmillNotFoundError:
                resolved[selection.key] = ResolvedRunnable(selection, False, "missing")
                continue
            except WindmillAuthorizationError:
                resolved[selection.key] = ResolvedRunnable(selection, False, "unauthorized")
                continue
            except WindmillError as err:
                raise UpdateFailed("Unable to refresh Windmill runnables") from err
            resolved[selection.key] = ResolvedRunnable(
                selection,
                True,
                None if details.schema_supported else details.schema_reason,
                details,
            )
        return resolved


@dataclass(frozen=True, slots=True)
class RunnableRunState:
    """What is currently known about the runs of one selected runnable."""

    last_run: datetime | None = None
    last_state: JobState | None = None
    last_duration_ms: int | None = None
    running: bool = False
    next_run: datetime | None = None

    def with_observation(self, jobs: Sequence[WindmillJob]) -> RunnableRunState:
        """Return this state advanced by one observation of a single runnable's jobs.

        The completion only ever moves forward. Both tiers hand their rows to this method, and
        the slow one may well be answering with a window the fast one has already overtaken.

        The running state and the next run are the opposite: they are re-derived from every
        observation, never carried over. A schedule that was disabled has to stop being
        announced, and it stops by its queued row disappearing.
        """
        running = any(job.state is JobState.RUNNING for job in jobs)
        next_run = _earliest_scheduled(jobs)
        completions = [
            (job.completed_at, job.id, job)
            for job in jobs
            if job.is_completed and job.completed_at is not None
        ]
        if not completions:
            return replace(self, running=running, next_run=next_run)
        completed_at, _, latest = max(completions, key=lambda entry: (entry[0], entry[1]))
        if self.last_run is not None and completed_at <= self.last_run:
            return replace(self, running=running, next_run=next_run)
        return RunnableRunState(
            last_run=completed_at,
            last_state=latest.state,
            last_duration_ms=latest.duration_ms,
            running=running,
            next_run=next_run,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the JSON-serializable part of this state.

        `running` and `next_run` are deliberately absent: both describe what Windmill is doing
        right now, and a restart is exactly the moment when a restored value would start lying
        about a job that finished or a schedule that was turned off in the meantime.
        """
        return {
            "last_run": _isoformat(self.last_run),
            "last_state": None if self.last_state is None else self.last_state.value,
            "last_duration_ms": self.last_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Any) -> RunnableRunState:
        """Restore one stored state, discarding anything unreadable."""
        if not isinstance(data, dict):
            return cls()
        raw_state = data.get("last_state")
        try:
            last_state = None if raw_state is None else JobState(str(raw_state))
        except ValueError:
            last_state = None
        duration = data.get("last_duration_ms")
        return cls(
            last_run=_parse_stored_timestamp(data.get("last_run")),
            last_state=last_state,
            last_duration_ms=duration if isinstance(duration, int) else None,
        )


type RunnableRunStates = Mapping[tuple[str, str], RunnableRunState]


class WindmillRunnableRunCoordinator(WindmillCoordinator[RunnableRunStates]):
    """Observe the run history of each selected runnable in two tiers.

    The slow tier asks Windmill for exactly one runnable's jobs, which is the only way to learn
    about a job that last ran long enough ago to have fallen out of the shared window. The fast
    tier is that shared window: `WindmillRunCoordinator` hands over every row it parsed, so a
    completion becomes visible in the minute it happens rather than at the next slow refresh.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        client: WindmillClient,
        store: Store[dict[str, Any]],
        selections: tuple[RunnableSelection, ...],
        restored: Mapping[tuple[str, str], RunnableRunState],
    ) -> None:
        """Initialize the config-entry-owned run-detail coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} runnable runs",
            config_entry=entry,
            update_interval=RUNNABLE_RUN_UPDATE_INTERVAL,
        )
        self.client = client
        self.selections = selections
        self._store = store
        # A removed selection must not keep its record alive, so the restored state is
        # projected onto the current selection instead of being merged with it.
        self._states: dict[tuple[str, str], RunnableRunState] = {
            selection.key: restored.get(selection.key, RunnableRunState())
            for selection in selections
        }
        self.data = dict(self._states)

    async def _async_observe(self) -> Mapping[tuple[str, str], RunnableRunState]:
        """Read one exact job window per selected runnable."""
        for selection in self.selections:
            try:
                jobs = await self.client.async_list_runnable_jobs(
                    selection.path, PageRequest(page=1, per_page=RUNNABLE_RUN_PAGE_SIZE)
                )
            except WindmillAuthenticationError as err:
                raise ConfigEntryAuthFailed("Windmill authentication failed") from err
            except WindmillError as err:
                raise UpdateFailed("Unable to refresh Windmill runnable runs") from err
            self._states[selection.key] = self._states[selection.key].with_observation(
                [job for job in jobs if (job.kind, job.path) == selection.key]
            )
        await self._async_save()
        return dict(self._states)

    async def async_apply_window(self, jobs: tuple[WindmillJob, ...]) -> None:
        """Fold the shared run window into the per-runnable states.

        This deliberately does not call `async_set_updated_data`: that would reschedule the
        next refresh, and a window arriving every minute would push the exact read past its
        interval forever. Listeners are notified directly instead.
        """
        by_key: dict[tuple[str, str], list[WindmillJob]] = {key: [] for key in self._states}
        for job in jobs:
            if job.path is None:
                continue
            rows = by_key.get((job.kind, job.path))
            if rows is not None:
                rows.append(job)
        changed = False
        for key, rows in by_key.items():
            advanced = self._states[key].with_observation(rows)
            if advanced != self._states[key]:
                self._states[key] = advanced
                changed = True
        if not changed:
            return
        self.data = dict(self._states)
        self.async_update_listeners()
        await self._async_save()

    async def _async_save(self) -> None:
        """Persist the bounded per-runnable state."""
        await self._store.async_save(
            {"runnables": {_state_key(key): state.as_dict() for key, state in self._states.items()}}
        )


def _earliest_scheduled(jobs: Sequence[WindmillJob]) -> datetime | None:
    """Return when this runnable is due to run next, if Windmill has reserved a slot.

    Only a queued row counts: a running job carries the time it was scheduled for, which is in
    the past by definition. A queued row whose slot has already passed is a job waiting for a
    free worker, not a future run.
    """
    now = dt_util.utcnow()
    upcoming = [
        job.scheduled_for
        for job in jobs
        if job.state is JobState.QUEUED
        and job.scheduled_for is not None
        and job.scheduled_for > now
    ]
    return min(upcoming) if upcoming else None


def _state_key(key: tuple[str, str]) -> str:
    """Return the storage key of one selection identity."""
    return f"{key[0]}:{key[1]}"


def load_runnable_run_states(raw: Any) -> Mapping[tuple[str, str], RunnableRunState]:
    """Read the stored per-runnable states, discarding unreadable entries."""
    rows = raw.get("runnables") if isinstance(raw, dict) else None
    if not isinstance(rows, dict):
        return {}
    restored: dict[tuple[str, str], RunnableRunState] = {}
    for stored_key, value in rows.items():
        kind, separator, path = str(stored_key).partition(":")
        if not separator:
            continue
        restored[(kind, path)] = RunnableRunState.from_dict(value)
    return restored


async def async_discover_runnables(client: WindmillClient) -> tuple[WindmillRunnable, ...]:
    """List bounded scripts and flows for the selection form."""
    discovered: list[WindmillRunnable] = []
    for kind in (RunnableKind.SCRIPT, RunnableKind.FLOW):
        try:
            for page in range(1, MAX_RUNNABLE_PAGES + 1):
                found = await client.async_list_runnables(
                    kind, PageRequest(page=page, per_page=RUNNABLE_PAGE_SIZE)
                )
                discovered.extend(found)
                if len(found) < RUNNABLE_PAGE_SIZE:
                    break
        except WindmillError:
            _LOGGER.debug("Windmill %s discovery is currently unavailable", kind.value)
    return tuple(discovered)


@dataclass(frozen=True, slots=True)
class TrackedJob:
    """One job that Home Assistant started, tracked until completion or expiry."""

    job_id: str
    kind: str
    path: str
    started_at: datetime

    def as_dict(self) -> dict[str, str]:
        """Return the JSON-serializable tracked job."""
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "path": self.path,
            "started_at": self.started_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Any) -> TrackedJob | None:
        """Restore one tracked job, ignoring anything unreadable."""
        if not isinstance(data, dict):
            return None
        started_at = _parse_stored_timestamp(data.get("started_at"))
        job_id = data.get("job_id")
        if started_at is None or not isinstance(job_id, str):
            return None
        return cls(
            job_id=job_id,
            kind=str(data.get("kind", "")),
            path=str(data.get("path", "")),
            started_at=started_at,
        )


class StartedJobRegistry:
    """Bounded registry of Home Assistant-started jobs with explicit expiry."""

    def __init__(self, store: Store[dict[str, Any]]) -> None:
        """Initialize an empty registry backed by one config-entry store."""
        self._store = store
        self._jobs: dict[str, TrackedJob] = {}
        # Every mutation is followed by a write of the whole registry, so concurrent callers
        # must be serialized to keep the stored registry consistent with this one.
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        """Restore the registry, discarding unreadable or expired entries."""
        async with self._lock:
            data = await self._store.async_load()
            rows = data.get("jobs") if isinstance(data, dict) else None
            if isinstance(rows, list):
                for row in rows[-MAX_TRACKED_JOBS:]:
                    job = TrackedJob.from_dict(row)
                    if job is not None:
                        self._jobs[job.job_id] = job
            self._prune()

    async def async_track(self, job: TrackedJob) -> None:
        """Record one started job and persist the bounded registry."""
        async with self._lock:
            self._jobs[job.job_id] = job
            self._prune()
            await self._async_save()

    async def async_forget(self, *job_ids: str) -> None:
        """Drop completed jobs from the registry in one bounded write."""
        async with self._lock:
            dropped = [job_id for job_id in job_ids if self._jobs.pop(job_id, None) is not None]
            if dropped:
                await self._async_save()

    def get(self, job_id: str) -> TrackedJob | None:
        """Return one tracked job, if Home Assistant started it."""
        self._prune()
        return self._jobs.get(job_id)

    @property
    def tracked(self) -> tuple[TrackedJob, ...]:
        """Return every currently tracked job."""
        self._prune()
        return tuple(self._jobs.values())

    def _prune(self) -> None:
        """Enforce the retention window and the size bound."""
        cutoff = dt_util.utcnow() - timedelta(hours=TRACKED_JOB_TTL_HOURS)
        fresh = [job for job in self._jobs.values() if job.started_at > cutoff]
        fresh.sort(key=lambda job: job.started_at)
        self._jobs = {job.job_id: job for job in fresh[-MAX_TRACKED_JOBS:]}

    async def _async_save(self) -> None:
        """Persist the bounded registry."""
        await self._store.async_save({"jobs": [job.as_dict() for job in self.tracked]})


class WindmillUpdateCoordinator(WindmillCoordinator[WindmillUpdateStatus | None]):
    """Poll the best-effort update check without blocking health updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        client: WindmillClient,
    ) -> None:
        """Initialize the config-entry-owned update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} update",
            config_entry=entry,
            update_interval=UPDATE_CHECK_INTERVAL,
        )
        self.client = client

    async def _async_observe(self) -> WindmillUpdateStatus:
        """Refresh the best-effort update check.

        The data type is optional because the first refresh may fail without failing setup:
        the upstream check depends on GitHub availability.
        """
        try:
            return await self.client.async_get_update_status()
        except WindmillAuthenticationError as err:
            raise ConfigEntryAuthFailed("Windmill authentication failed") from err
        except WindmillError as err:
            raise UpdateFailed("Unable to refresh the Windmill update check") from err
