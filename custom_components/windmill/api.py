"""Asynchronous, Home Assistant-independent Windmill API client."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, TypeIs
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from uuid import UUID

import aiohttp

from .const import DEFAULT_CONNECT_TIMEOUT, DEFAULT_REQUEST_TIMEOUT, MAX_RESPONSE_BYTES

MAX_PAGE_SIZE = 100
MAX_RETRY_AFTER = 300.0
MAX_WORKSPACE_ROWS = 200
MAX_WORKER_GROUP_ROWS = 200
# `jobs/list` is a `queue UNION ALL completed` whose union carries no limit: `per_page` bounds
# only the completed half, so the response also contains every queued and running top-level job.
# The row bound must therefore be a client-side maximum, never the requested page size. The
# transport's MAX_RESPONSE_BYTES stays the outer guarantee and rejects a larger queue first.
MAX_JOB_ROWS = 200
MAX_TEXT_FIELD_LENGTH = 256
ALIVE_WORKER_SECONDS = 300
CANCELLATION_REASON = "Canceled from Home Assistant"
UPDATE_TEXT_RE = re.compile(r"Update:\s+(?P<installed>\S+)\s+->\s+(?P<latest>\S+)")
VERSION_RE = re.compile(r"v?\d+(?:\.\d+){0,3}(?:[-+][A-Za-z0-9.-]{1,32})?")
MANAGED_CLOUD_HOST = "windmill.dev"
RELEASE_URL_TEMPLATE = "https://github.com/windmill-labs/windmill/releases/tag/v{version}"
MAX_RUNNABLE_PARAMETERS = 50
MAX_ENUM_VALUES = 20
RUNNABLE_PATH_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.\-]*)*")
SUPPORTED_PARAMETER_TYPES = frozenset({"string", "number", "integer", "boolean", "array", "object"})


class WindmillError(Exception):
    """Base exception for the Windmill client."""


class WindmillUrlError(WindmillError):
    """Raised when a base URL is invalid or unsafe."""


class WindmillConnectionError(WindmillError):
    """Raised when Windmill cannot be reached."""


class WindmillTimeoutError(WindmillConnectionError):
    """Raised when a Windmill request exceeds its deadline."""


class WindmillAuthenticationError(WindmillError):
    """Raised when Windmill rejects the token."""


class WindmillAuthorizationError(WindmillError):
    """Raised when the token lacks permission for an operation."""


class WindmillWorkspaceError(WindmillError):
    """Raised when the configured workspace is unavailable."""


class WindmillNotFoundError(WindmillError):
    """Raised when a requested endpoint or resource is unavailable."""


class WindmillRequestError(WindmillError):
    """Raised when Windmill rejects a request."""


class WindmillConflictError(WindmillError):
    """Raised when a Windmill request conflicts with current state."""


class WindmillRateLimitError(WindmillError):
    """Raised when Windmill rate-limits a request."""

    def __init__(
        self,
        message: str = "Windmill rate limited the request",
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class WindmillServerError(WindmillError):
    """Raised when Windmill reports a server failure."""


class WindmillProtocolError(WindmillError):
    """Raised when Windmill returns an unexpected response contract."""


class WindmillEdition(StrEnum):
    """Edition labels verified in the Windmill version response."""

    COMMUNITY = "ce"
    ENTERPRISE = "ee"


class WindmillHealthState(StrEnum):
    """Bounded states returned by Windmill health endpoints."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class CapabilityStatus(StrEnum):
    """Stable five-state capability lattice."""

    AVAILABLE = "available"
    UNAUTHORIZED = "unauthorized"
    UNSUPPORTED = "unsupported"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    NOT_APPLICABLE = "not_applicable"


class CapabilityReason(StrEnum):
    """Bounded reasons for capability decisions."""

    PROBE_SUCCEEDED = "probe_succeeded"
    PERMISSION_DENIED = "permission_denied"
    ENDPOINT_MISSING = "endpoint_missing"
    TEMPORARY_FAILURE = "temporary_failure"
    UNEXPECTED_RESPONSE = "unexpected_response"
    CONTEXT_REQUIRED = "context_required"


@dataclass(frozen=True, slots=True)
class WindmillIdentity:
    """Bounded identity fields returned by the Windmill whoami endpoint."""

    username: str
    is_admin: bool
    is_super_admin: bool


@dataclass(frozen=True, slots=True)
class WindmillServerInfo:
    """Allowlisted facts parsed from the public version endpoint."""

    edition: WindmillEdition
    version: str


@dataclass(frozen=True, slots=True)
class WindmillWorkspaceInfo:
    """Bounded non-sensitive projection of one visible workspace."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class WindmillConnection:
    """Validated connection facts retained by config-entry runtime data."""

    identity: WindmillIdentity
    server: WindmillServerInfo


@dataclass(frozen=True, slots=True)
class WindmillHealthStatus:
    """Bounded projection of the coarse health response."""

    status: WindmillHealthState
    checked_at: datetime
    database_healthy: bool
    workers_alive: int


@dataclass(frozen=True, slots=True)
class WindmillDetailedHealth:
    """Bounded projection of the authenticated detailed health response."""

    status: WindmillHealthState
    checked_at: datetime
    database_healthy: bool
    workers_alive: int | None
    pending_jobs: int | None
    running_jobs: int | None


@dataclass(frozen=True, slots=True)
class WindmillUpdateStatus:
    """Bounded projection of the best-effort update check."""

    installed_version: str | None
    latest_version: str | None
    up_to_date: bool


class RunnableKind(StrEnum):
    """Kinds of Windmill runnables this integration can address."""

    SCRIPT = "script"
    FLOW = "flow"


class AddressingMode(StrEnum):
    """How a selected runnable is addressed at execution time."""

    LATEST = "latest"
    PINNED = "pinned"


@dataclass(frozen=True, slots=True)
class WindmillRunnable:
    """Bounded discovery projection of one script or flow."""

    kind: RunnableKind
    path: str
    summary: str


@dataclass(frozen=True, slots=True)
class RunnableParameter:
    """Bounded projection of one input-schema parameter."""

    name: str
    type: str
    required: bool
    enum: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class RunnableDetails:
    """Bounded detail projection used to decide addressing and argument support."""

    kind: RunnableKind
    path: str
    summary: str
    script_hash: str | None
    flow_version: int | None
    parameters: tuple[RunnableParameter, ...]
    schema_supported: bool
    schema_reason: str | None = None


class JobState(StrEnum):
    """Bounded run states derived from the job union."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELED = "canceled"


# The terminal states, in the order the enum sensor offers them. One definition, because a
# stored "last status" and the options of the entity reporting it must not drift apart.
COMPLETION_STATES: tuple[JobState, ...] = (JobState.SUCCESS, JobState.FAILURE, JobState.CANCELED)


@dataclass(frozen=True, slots=True)
class WindmillJob:
    """Bounded non-sensitive projection of one top-level job."""

    id: str
    state: JobState
    kind: str
    path: str | None
    created_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    # Windmill writes the next occurrence of a schedule into the queue as a real job, so a
    # queued row with a future `scheduled_for` is that schedule's next run. Completed rows
    # never carry one: the completed half of the union selects it as null.
    scheduled_for: datetime | None = None

    @property
    def is_completed(self) -> bool:
        """Return whether the job reached a terminal state."""
        return self.state in COMPLETION_STATES


@dataclass(frozen=True, slots=True)
class WindmillWorker:
    """Bounded non-sensitive projection of one alive worker ping."""

    name: str
    instance: str
    group: str
    version: str


@dataclass(frozen=True, slots=True)
class PageRequest:
    """Validated Windmill page parameters shared by bounded list operations."""

    page: int = 1
    per_page: int = 30

    def __post_init__(self) -> None:
        if isinstance(self.page, bool) or not isinstance(self.page, int) or self.page < 1:
            raise ValueError("Page must be a positive integer")
        if (
            isinstance(self.per_page, bool)
            or not isinstance(self.per_page, int)
            or not 1 <= self.per_page <= MAX_PAGE_SIZE
        ):
            raise ValueError(f"Page size must be between 1 and {MAX_PAGE_SIZE}")

    def as_params(self) -> dict[str, int]:
        """Return query parameters for a Windmill list request."""
        return {"page": self.page, "per_page": self.per_page}


@dataclass(frozen=True, slots=True)
class CapabilityAvailability:
    """One capability state with a bounded non-sensitive reason."""

    status: CapabilityStatus
    reason: CapabilityReason


@dataclass(frozen=True, slots=True)
class CapabilityMatrix:
    """Explicit capabilities consumed by later Home Assistant platforms."""

    health: CapabilityAvailability
    detailed_health: CapabilityAvailability
    workers: CapabilityAvailability
    runs: CapabilityAvailability
    script_discovery: CapabilityAvailability
    flow_discovery: CapabilityAvailability
    script_execution: CapabilityAvailability
    flow_execution: CapabilityAvailability
    cancellation: CapabilityAvailability
    update_visibility: CapabilityAvailability


@dataclass(frozen=True, slots=True)
class _WindmillResponse:
    """Bounded internal response representation."""

    status: int
    content_type: str
    payload: bytes
    retry_after: float | None


def _is_loopback(host: str) -> bool:
    """Return whether a hostname is unambiguously local to the HA host."""
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_insecure_transport(base_url: str) -> bool:
    """Return whether a base URL sends the token unencrypted across a network.

    Plain HTTP is accepted for self-hosted instances that have no certificate, because a LAN
    hostname cannot be told apart from a public one at validation time. Loopback is exempt:
    those bytes never leave the Home Assistant host, so there is nothing to intercept.
    """
    parts = urlsplit(base_url)
    return parts.scheme == "http" and not _is_loopback(parts.hostname or "")


def _is_bounded_text(value: Any) -> TypeIs[str]:
    """Return whether an untrusted value is a short non-empty string."""
    return isinstance(value, str) and bool(value.strip()) and len(value) <= MAX_TEXT_FIELD_LENGTH


def _is_count(value: Any) -> TypeIs[int]:
    """Return whether an untrusted value is a non-negative integer count."""
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _is_uuid(value: Any) -> TypeIs[str]:
    """Return whether an untrusted value is a canonical UUID string."""
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value.lower()
    except ValueError:
        return False


def normalize_base_url(value: str) -> str:
    """Normalize and validate a Windmill base URL.

    Both HTTP and HTTPS are accepted; `is_insecure_transport` classifies the result so the
    unencrypted case surfaces as a repair issue instead of a rejected config flow. TLS
    verification for HTTPS is untouched, and every structural rule below still holds.
    """
    if not isinstance(value, str) or not value.strip():
        raise WindmillUrlError("Base URL is required")

    raw_value = value.strip()
    try:
        parts = urlsplit(raw_value)
        port = parts.port
    except ValueError as err:
        raise WindmillUrlError("Base URL is invalid") from err

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.hostname:
        raise WindmillUrlError("Base URL must use HTTP or HTTPS")
    if parts.username is not None or parts.password is not None:
        raise WindmillUrlError("Base URL must not contain credentials")
    if parts.query or parts.fragment:
        raise WindmillUrlError("Base URL must not contain a query or fragment")

    try:
        host = parts.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as err:
        raise WindmillUrlError("Base URL hostname is invalid") from err
    if not host:
        raise WindmillUrlError("Base URL hostname is required")

    path_segments: list[str] = []
    for raw_segment in parts.path.split("/"):
        if not raw_segment:
            continue
        try:
            segment = unquote(raw_segment, errors="strict")
        except UnicodeDecodeError as err:
            raise WindmillUrlError("Base URL path encoding is invalid") from err
        if (
            segment in {".", ".."}
            or "/" in segment
            or "\\" in segment
            or any(ord(char) < 32 or ord(char) == 127 for char in segment)
        ):
            raise WindmillUrlError("Base URL path contains an unsafe segment")
        path_segments.append(quote(segment, safe="!$&'()*+,-.:;=@_~"))
    path = f"/{'/'.join(path_segments)}" if path_segments else ""

    default_port = 443 if scheme == "https" else 80
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port in {None, default_port} else f"{display_host}:{port}"
    return urlunsplit((scheme, netloc, path, "", ""))


def is_managed_cloud(base_url: str) -> bool:
    """Return whether a base URL points at the managed Windmill Cloud deployment."""
    host = urlsplit(base_url).hostname or ""
    return host == MANAGED_CLOUD_HOST or host.endswith(f".{MANAGED_CLOUD_HOST}")


def release_url(version: str | None) -> str | None:
    """Return a release URL only for a version string that is safe to interpolate."""
    if version is None or VERSION_RE.fullmatch(version) is None:
        return None
    return RELEASE_URL_TEMPLATE.format(version=version.removeprefix("v"))


def normalize_runnable_path(value: str) -> str:
    """Validate a Windmill runnable path before it is used to build a URL."""
    if not isinstance(value, str):
        raise WindmillRequestError("Runnable path is required")
    path = value.strip().strip("/")
    if not path or len(path) > MAX_TEXT_FIELD_LENGTH:
        raise WindmillRequestError("Runnable path is invalid")
    if RUNNABLE_PATH_RE.fullmatch(path) is None or ".." in path.split("/"):
        raise WindmillRequestError("Runnable path is invalid")
    return path


def normalize_workspace(value: str) -> str:
    """Normalize a workspace identifier for storage and URL construction."""
    if not isinstance(value, str):
        raise WindmillWorkspaceError("Workspace is required")
    workspace = value.strip()
    if (
        not workspace
        or len(workspace) > MAX_TEXT_FIELD_LENGTH
        or any(ord(c) < 32 for c in workspace)
    ):
        raise WindmillWorkspaceError("Workspace is invalid")
    return workspace


class WindmillInstanceClient:
    """Typed asynchronous transport for instance-scoped Windmill endpoints."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        token: str,
        *,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize the transport with a normalized non-secret base URL."""
        self._session = session
        self.base_url = normalize_base_url(base_url)
        if not isinstance(token, str) or not token:
            raise WindmillAuthenticationError("Token is required")
        self._token = token
        self._timeout = aiohttp.ClientTimeout(total=request_timeout, connect=connect_timeout)

    async def async_get_server_info(self) -> WindmillServerInfo:
        """Read and parse the public Windmill version endpoint."""
        response = await self._async_get(
            "/api/version",
            authenticated=False,
            accept="text/plain",
        )
        if response.status in {401, 403, 404}:
            raise WindmillProtocolError("Windmill version endpoint is unavailable")
        self._raise_for_status(response, not_found=WindmillNotFoundError)
        self._require_content_type(response, "text/plain")
        try:
            value = response.payload.decode("utf-8").strip()
        except UnicodeDecodeError as err:
            raise WindmillProtocolError("Windmill returned an invalid version") from err
        match = re.fullmatch(r"(?P<edition>CE|EE)\s+(?P<version>\S+)", value)
        if match is None or len(match.group("version")) > 128:
            raise WindmillProtocolError("Windmill returned an invalid version")
        edition = (
            WindmillEdition.COMMUNITY
            if match.group("edition") == "CE"
            else WindmillEdition.ENTERPRISE
        )
        return WindmillServerInfo(edition=edition, version=match.group("version"))

    async def async_list_workspaces(self) -> tuple[WindmillWorkspaceInfo, ...]:
        """Return the bounded set of workspaces visible to the configured token.

        This is instance-scoped, so a workspace-bound token is refused with `401`. That is a
        denial of this endpoint, not a rejected credential, and callers fall back to manual
        workspace entry (WMHA-0045).
        """
        response = await self._async_get(
            "/api/workspaces/list",
            authenticated=True,
            accept="application/json",
        )
        self._raise_for_status(
            response,
            not_found=WindmillNotFoundError,
            authentication_required=False,
        )
        return self._parse_workspaces(self._decode_json(response))

    async def async_get_health_status(self) -> WindmillHealthStatus:
        """Return the bounded public coarse-health projection."""
        response = await self._async_get(
            "/api/health/status",
            authenticated=False,
            accept="application/json",
            params={"force": "false"},
            body_statuses=frozenset({200, 503}),
        )
        self._raise_for_status(
            response,
            success_statuses=frozenset({200, 503}),
            not_found=WindmillNotFoundError,
            authentication_required=False,
        )
        return self._parse_health_status(self._decode_json(response))

    async def async_get_detailed_health(self) -> WindmillDetailedHealth:
        """Return the bounded authenticated detailed-health projection."""
        response = await self._async_get(
            "/api/health/detailed",
            authenticated=True,
            accept="application/json",
            body_statuses=frozenset({200, 503}),
        )
        self._raise_for_status(
            response,
            success_statuses=frozenset({200, 503}),
            not_found=WindmillNotFoundError,
        )
        return self._parse_detailed_health(self._decode_json(response))

    async def async_list_workers(
        self, page: PageRequest, *, ping_since: int = ALIVE_WORKER_SECONDS
    ) -> tuple[WindmillWorker, ...]:
        """Return one bounded page of alive workers without any sensitive field."""
        response = await self._async_get(
            "/api/workers/list",
            authenticated=True,
            accept="application/json",
            params={**page.as_params(), "ping_since": ping_since},
        )
        self._raise_for_status(response, not_found=WindmillNotFoundError)
        return self._parse_workers(self._decode_json(response), page.per_page)

    async def async_list_worker_groups(self) -> tuple[str, ...]:
        """Return the configured worker-group names and discard their configuration."""
        response = await self._async_get(
            "/api/configs/list_worker_groups",
            authenticated=True,
            accept="application/json",
        )
        self._raise_for_status(response, not_found=WindmillNotFoundError)
        return self._parse_worker_groups(self._decode_json(response))

    async def async_get_update_status(self) -> WindmillUpdateStatus:
        """Return the bounded best-effort update check of a self-hosted deployment."""
        response = await self._async_get(
            "/api/uptodate",
            authenticated=False,
            accept="text/plain",
        )
        self._raise_for_status(
            response,
            not_found=WindmillNotFoundError,
            authentication_required=False,
        )
        self._require_content_type(response, "text/plain")
        try:
            value = response.payload.decode("utf-8").strip()
        except UnicodeDecodeError as err:
            raise WindmillProtocolError("Windmill returned an invalid update status") from err
        if value == "yes":
            return WindmillUpdateStatus(
                installed_version=None, latest_version=None, up_to_date=True
            )
        match = UPDATE_TEXT_RE.fullmatch(value)
        if match is None:
            raise WindmillProtocolError("Windmill returned an invalid update status")
        installed = match.group("installed")
        latest = match.group("latest")
        if len(installed) > 128 or len(latest) > 128:
            raise WindmillProtocolError("Windmill returned an invalid update status")
        return WindmillUpdateStatus(
            installed_version=installed,
            latest_version=latest,
            up_to_date=installed == latest,
        )

    async def _probe_update_visibility(self) -> CapabilityAvailability:
        """Probe only the bounded update-check contract, not deployment eligibility."""

        async def validate() -> None:
            response = await self._async_get(
                "/api/uptodate",
                authenticated=False,
                accept="text/plain",
            )
            self._raise_for_status(
                response,
                not_found=WindmillNotFoundError,
                authentication_required=False,
            )
            self._require_content_type(response, "text/plain")
            try:
                value = response.payload.decode("utf-8").strip()
            except UnicodeDecodeError as err:
                raise WindmillProtocolError("Windmill returned an invalid update status") from err
            if value != "yes" and re.fullmatch(r"Update:\s+\S+\s+->\s+\S+", value) is None:
                raise WindmillProtocolError("Windmill returned an invalid update status")

        return await self._probe(validate())

    async def _probe(self, operation: Awaitable[object]) -> CapabilityAvailability:
        """Convert optional endpoint outcomes into the capability lattice."""
        try:
            await operation
        except WindmillAuthenticationError:
            raise
        except WindmillAuthorizationError:
            return CapabilityAvailability(
                CapabilityStatus.UNAUTHORIZED,
                CapabilityReason.PERMISSION_DENIED,
            )
        except WindmillNotFoundError:
            return CapabilityAvailability(
                CapabilityStatus.UNSUPPORTED,
                CapabilityReason.ENDPOINT_MISSING,
            )
        except (
            WindmillConnectionError,
            WindmillRateLimitError,
            WindmillServerError,
        ):
            return CapabilityAvailability(
                CapabilityStatus.TEMPORARILY_UNAVAILABLE,
                CapabilityReason.TEMPORARY_FAILURE,
            )
        except (
            WindmillConflictError,
            WindmillProtocolError,
            WindmillRequestError,
        ):
            return CapabilityAvailability(
                CapabilityStatus.UNSUPPORTED,
                CapabilityReason.UNEXPECTED_RESPONSE,
            )
        return CapabilityAvailability(
            CapabilityStatus.AVAILABLE,
            CapabilityReason.PROBE_SUCCEEDED,
        )

    async def _async_get(
        self,
        path: str,
        *,
        authenticated: bool,
        accept: str,
        params: Mapping[str, str | int] | None = None,
        body_statuses: frozenset[int] = frozenset({200}),
    ) -> _WindmillResponse:
        """GET one bounded response through the central transport path."""
        return await self._async_request(
            "GET",
            path,
            authenticated=authenticated,
            accept=accept,
            params=params,
            body_statuses=body_statuses,
        )

    async def _async_post(
        self,
        path: str,
        *,
        accept: str,
        json_body: Mapping[str, Any],
        body_statuses: frozenset[int] = frozenset({200, 201}),
    ) -> _WindmillResponse:
        """POST one bounded authenticated request through the central transport path."""
        return await self._async_request(
            "POST",
            path,
            authenticated=True,
            accept=accept,
            json_body=json_body,
            body_statuses=body_statuses,
        )

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool,
        accept: str,
        params: Mapping[str, str | int] | None = None,
        json_body: Mapping[str, Any] | None = None,
        body_statuses: frozenset[int] = frozenset({200}),
    ) -> _WindmillResponse:
        """Perform one bounded request and read at most the response limit."""
        if not path.startswith("/") or "?" in path or "#" in path:
            raise WindmillProtocolError("Windmill client path is invalid")
        headers = {"Accept": accept}
        if authenticated:
            headers["Authorization"] = f"Bearer {self._token}"

        send = self._session.post if method == "POST" else self._session.get
        try:
            async with send(
                f"{self.base_url}{path}",
                headers=headers,
                params=params,
                json=json_body,
                timeout=self._timeout,
                allow_redirects=False,
            ) as response:
                retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
                if response.status not in body_statuses:
                    return _WindmillResponse(response.status, "", b"", retry_after)
                content_type = (
                    response.headers.get("Content-Type", "").partition(";")[0].strip().lower()
                )
                content_length = response.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        length = int(content_length)
                    except ValueError as err:
                        raise WindmillProtocolError(
                            "Windmill returned an invalid content length"
                        ) from err
                    if length < 0 or length > MAX_RESPONSE_BYTES:
                        raise WindmillProtocolError("Windmill response is too large")
                payload_buffer = bytearray()
                content = response.content
                while True:
                    remaining = MAX_RESPONSE_BYTES + 1 - len(payload_buffer)
                    chunk = await content.read(min(8192, remaining))
                    if not chunk:
                        break
                    payload_buffer.extend(chunk)
                    if len(payload_buffer) > MAX_RESPONSE_BYTES:
                        raise WindmillProtocolError("Windmill response is too large")
        except TimeoutError as err:
            raise WindmillTimeoutError("Windmill request timed out") from err
        except aiohttp.ClientError as err:
            raise WindmillConnectionError("Unable to connect to Windmill") from err

        return _WindmillResponse(response.status, content_type, bytes(payload_buffer), retry_after)

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        """Parse only bounded delta-seconds from an untrusted Retry-After header."""
        if value is None:
            return None
        try:
            retry_after = float(value)
        except ValueError:
            return None
        if not 0 <= retry_after <= MAX_RETRY_AFTER:
            return None
        return retry_after

    @staticmethod
    def _raise_for_status(
        response: _WindmillResponse,
        *,
        success_statuses: frozenset[int] = frozenset({200}),
        not_found: type[WindmillError],
        authentication_required: bool = True,
    ) -> None:
        """Map HTTP statuses to the stable typed client taxonomy.

        Set `authentication_required=False` for an endpoint whose `401` says nothing about
        the credential itself: a public endpoint, or an instance-scoped one that a
        workspace-bound token simply cannot address. Windmill Cloud answers `401` rather
        than `403` in that second case (WMHA-0045), so only a workspace-scoped endpoint may
        treat `401` as proof that the token is bad.
        """
        status = response.status
        if status in success_statuses:
            return
        if status == 401:
            if authentication_required:
                raise WindmillAuthenticationError("Windmill rejected the token")
            raise WindmillAuthorizationError("Windmill denied the probe for this token")
        if status == 403:
            raise WindmillAuthorizationError("Windmill denied the request")
        if status == 404:
            raise not_found("Windmill endpoint or resource was not found")
        if status == 409:
            raise WindmillConflictError("Windmill request conflicts with current state")
        if status == 429:
            raise WindmillRateLimitError(retry_after=response.retry_after)
        if status in {400, 422}:
            raise WindmillRequestError("Windmill rejected the request")
        if 500 <= status <= 599:
            raise WindmillServerError("Windmill server error")
        raise WindmillProtocolError("Windmill returned an unexpected status")

    @staticmethod
    def _require_content_type(response: _WindmillResponse, expected: str) -> None:
        """Require an exact or structured-suffix response content type."""
        if response.content_type == expected:
            return
        if expected == "application/json" and response.content_type.endswith("+json"):
            return
        raise WindmillProtocolError("Windmill returned an unexpected content type")

    @classmethod
    def _decode_json(cls, response: _WindmillResponse) -> Any:
        """Decode one bounded JSON success response."""
        cls._require_content_type(response, "application/json")
        try:
            return json.loads(response.payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise WindmillProtocolError("Windmill returned invalid JSON") from err

    @staticmethod
    def _parse_workspaces(data: Any) -> tuple[WindmillWorkspaceInfo, ...]:
        """Allowlist the bounded identity and label of every visible workspace."""
        if not isinstance(data, list) or len(data) > MAX_WORKSPACE_ROWS:
            raise WindmillProtocolError("Windmill returned an invalid workspace list")
        workspaces: list[WindmillWorkspaceInfo] = []
        for row in data:
            if not isinstance(row, dict):
                raise WindmillProtocolError("Windmill returned an invalid workspace")
            identifier = row.get("id")
            name = row.get("name", identifier)
            if not _is_bounded_text(identifier) or not _is_bounded_text(name):
                raise WindmillProtocolError("Windmill returned an invalid workspace")
            workspaces.append(WindmillWorkspaceInfo(id=identifier.strip(), name=name.strip()))
        return tuple(workspaces)

    @staticmethod
    def _parse_workers(data: Any, limit: int) -> tuple[WindmillWorker, ...]:
        """Allowlist four bounded worker fields and discard every other value."""
        if not isinstance(data, list) or len(data) > limit:
            raise WindmillProtocolError("Windmill returned an invalid worker list")
        workers: list[WindmillWorker] = []
        for row in data:
            if not isinstance(row, dict):
                raise WindmillProtocolError("Windmill returned an invalid worker")
            name = row.get("worker")
            instance = row.get("worker_instance")
            group = row.get("worker_group")
            version = row.get("wm_version")
            if not (
                _is_bounded_text(name)
                and _is_bounded_text(instance)
                and _is_bounded_text(group)
                and _is_bounded_text(version)
            ):
                raise WindmillProtocolError("Windmill returned an invalid worker")
            workers.append(
                WindmillWorker(
                    name=name.strip(),
                    instance=instance.strip(),
                    group=group.strip(),
                    version=version.strip(),
                )
            )
        return tuple(workers)

    @staticmethod
    def _parse_worker_groups(data: Any) -> tuple[str, ...]:
        """Keep only the bounded name of every configured worker group."""
        if not isinstance(data, list) or len(data) > MAX_WORKER_GROUP_ROWS:
            raise WindmillProtocolError("Windmill returned an invalid worker group list")
        groups: list[str] = []
        for row in data:
            if not isinstance(row, dict) or not _is_bounded_text(row.get("name")):
                raise WindmillProtocolError("Windmill returned an invalid worker group")
            name = str(row["name"]).strip()
            if name not in groups:
                groups.append(name)
        return tuple(groups)

    @classmethod
    def _parse_health_status(cls, data: Any) -> WindmillHealthStatus:
        """Allowlist and validate the coarse health response."""
        if not isinstance(data, dict):
            raise WindmillProtocolError("Windmill returned an invalid health status")
        raw_status = data.get("status")
        if not isinstance(raw_status, str):
            raise WindmillProtocolError("Windmill returned an invalid health state")
        try:
            status = WindmillHealthState(raw_status)
        except (TypeError, ValueError) as err:
            raise WindmillProtocolError("Windmill returned an invalid health state") from err
        checked_at = cls._parse_timestamp(data.get("checked_at"), "health")
        database_healthy = data.get("database_healthy")
        workers_alive = data.get("workers_alive")
        if not isinstance(database_healthy, bool):
            raise WindmillProtocolError("Windmill returned an invalid database health value")
        if not _is_count(workers_alive):
            raise WindmillProtocolError("Windmill returned an invalid worker count")
        return WindmillHealthStatus(
            status=status,
            checked_at=checked_at,
            database_healthy=database_healthy,
            workers_alive=workers_alive,
        )

    @classmethod
    def _parse_detailed_health(cls, data: Any) -> WindmillDetailedHealth:
        """Allowlist five bounded facts and discard the rest of detailed health."""
        if not isinstance(data, dict):
            raise WindmillProtocolError("Windmill returned an invalid detailed health response")
        raw_status = data.get("status")
        version = data.get("version")
        checks = data.get("checks")
        if not isinstance(raw_status, str) or raw_status not in set(WindmillHealthState):
            raise WindmillProtocolError("Windmill returned an invalid detailed health state")
        checked_at = cls._parse_timestamp(data.get("checked_at"), "detailed health")
        if not isinstance(version, str) or not version or len(version) > 128:
            raise WindmillProtocolError("Windmill returned an invalid detailed health version")
        if not isinstance(checks, dict):
            raise WindmillProtocolError("Windmill returned invalid detailed health checks")

        database = checks.get("database")
        if not isinstance(database, dict) or not isinstance(database.get("healthy"), bool):
            raise WindmillProtocolError("Windmill returned an invalid detailed database check")

        workers_alive = cls._optional_count(checks.get("workers"), "active_count", "workers")
        pending_jobs = cls._optional_count(checks.get("queue"), "pending_jobs", "queue")
        running_jobs = cls._optional_count(checks.get("queue"), "running_jobs", "queue")
        return WindmillDetailedHealth(
            status=WindmillHealthState(raw_status),
            checked_at=checked_at,
            database_healthy=database["healthy"],
            workers_alive=workers_alive,
            pending_jobs=pending_jobs,
            running_jobs=running_jobs,
        )

    @staticmethod
    def _optional_count(check: Any, field: str, name: str) -> int | None:
        """Read one bounded count from a nullable detailed-health check."""
        if check is None:
            return None
        if not isinstance(check, dict):
            raise WindmillProtocolError(f"Windmill returned an invalid detailed {name} check")
        value = check.get(field)
        if not _is_count(value):
            raise WindmillProtocolError(f"Windmill returned an invalid detailed {name} count")
        return value

    @staticmethod
    def _parse_timestamp(value: Any, endpoint: str) -> datetime:
        """Parse one bounded timezone-aware ISO-8601 timestamp."""
        if not isinstance(value, str) or not value or len(value) > 128:
            raise WindmillProtocolError(f"Windmill returned an invalid {endpoint} timestamp")
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as err:
            raise WindmillProtocolError(
                f"Windmill returned an invalid {endpoint} timestamp"
            ) from err
        if timestamp.tzinfo is None:
            raise WindmillProtocolError(f"Windmill returned an invalid {endpoint} timestamp")
        return timestamp


class WindmillClient(WindmillInstanceClient):
    """Typed asynchronous client for one verified Windmill workspace."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        workspace: str,
        token: str,
        *,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize the client with normalized non-secret connection identity."""
        super().__init__(
            session,
            base_url,
            token,
            connect_timeout=connect_timeout,
            request_timeout=request_timeout,
        )
        self.workspace = normalize_workspace(workspace)

    @property
    def identity_key(self) -> tuple[str, str]:
        """Return the stable non-secret identity used for duplicate detection."""
        return (self.base_url, self.workspace)

    async def async_connect(self) -> WindmillConnection:
        """Validate the deployment, token and workspace and return bounded facts."""
        server = await self.async_get_server_info()
        identity = await self._async_get_identity()
        return WindmillConnection(identity=identity, server=server)

    async def async_validate(self) -> WindmillIdentity:
        """Validate setup while preserving the WMHA-0002 client interface."""
        return (await self.async_connect()).identity

    async def async_discover_capabilities(self) -> CapabilityMatrix:
        """Probe a fixed set of safe read-only capabilities."""
        page = PageRequest(page=1, per_page=1)
        workspace = quote(self.workspace, safe="")
        runs_params: dict[str, str | int] = {
            **page.as_params(),
            "has_null_parent": "true",
            "is_flow_step": "false",
        }
        tasks = [
            asyncio.create_task(self._probe(self.async_get_health_status())),
            asyncio.create_task(
                self._probe_json_object(
                    "/api/health/detailed",
                    authenticated=True,
                    # Instance-scoped: a workspace-bound token is refused with 401 rather
                    # than 403 on Windmill Cloud, and that must degrade this optional
                    # capability instead of failing the credential (WMHA-0045).
                    authentication_required=False,
                    body_statuses=frozenset({200, 503}),
                    # v1.775.2 has no `health` scope domain, so its scope middleware
                    # rejects granular-scoped tokens with 400 before the handler
                    # (WMHA-0026 live verification); that is a scope denial, not a
                    # malformed request from this fixed parameterless probe.
                    scope_denied_statuses=frozenset({400}),
                )
            ),
            asyncio.create_task(
                self._probe_json_list(
                    "/api/workers/list",
                    params={**page.as_params(), "ping_since": 300},
                    # Instance-scoped, same 401 semantics as detailed health (WMHA-0045).
                    authentication_required=False,
                )
            ),
            asyncio.create_task(
                self._probe_json_list(
                    f"/api/w/{workspace}/jobs/list",
                    params=runs_params,
                    # The queued half of the union ignores `per_page`; one running job would
                    # otherwise turn a healthy endpoint into `unsupported` (WMHA-0038).
                    max_items=MAX_JOB_ROWS,
                )
            ),
            asyncio.create_task(
                self._probe_json_list(
                    f"/api/w/{workspace}/scripts/list",
                    params=page.as_params(),
                )
            ),
            asyncio.create_task(
                self._probe_json_list(
                    f"/api/w/{workspace}/flows/list",
                    params=page.as_params(),
                )
            ),
            asyncio.create_task(self._probe_update_visibility()),
        ]
        try:
            probes = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        health, detailed_health, workers, runs, scripts, flows, update_visibility = probes
        return CapabilityMatrix(
            health=health,
            detailed_health=detailed_health,
            workers=workers,
            runs=runs,
            script_discovery=scripts,
            flow_discovery=flows,
            script_execution=self._require_context(),
            flow_execution=self._require_context(),
            cancellation=self._require_context(),
            update_visibility=update_visibility,
        )

    async def async_list_jobs(self, page: PageRequest) -> tuple[WindmillJob, ...]:
        """Return one bounded page of top-level jobs without any sensitive payload."""
        workspace = quote(self.workspace, safe="")
        response = await self._async_get(
            f"/api/w/{workspace}/jobs/list",
            authenticated=True,
            accept="application/json",
            params={
                **page.as_params(),
                "has_null_parent": "true",
                "is_flow_step": "false",
            },
        )
        self._raise_for_status(response, not_found=WindmillNotFoundError)
        # Not `page.per_page`: the queued half of the union is not paginated, so a page
        # legitimately carries the requested completed rows plus the whole queue.
        return self._parse_jobs(self._decode_json(response), MAX_JOB_ROWS)

    async def async_list_runnable_jobs(
        self, path: str, page: PageRequest
    ) -> tuple[WindmillJob, ...]:
        """Return the jobs of exactly one runnable path, queued and completed alike.

        `script_path_exact` matches the unified `runnable_path` column, so one parameter
        addresses scripts and flows. It is deliberately the only filter sent besides the
        top-level ones: adding `success`, `status`, `completed_before` or any other filter of
        that family makes upstream answer from a completed-only query, which silently drops the
        running and scheduled jobs this read exists to see.
        """
        workspace = quote(self.workspace, safe="")
        response = await self._async_get(
            f"/api/w/{workspace}/jobs/list",
            authenticated=True,
            accept="application/json",
            params={
                **page.as_params(),
                "script_path_exact": normalize_runnable_path(path),
                "has_null_parent": "true",
                "is_flow_step": "false",
            },
        )
        self._raise_for_status(response, not_found=WindmillNotFoundError)
        return self._parse_jobs(self._decode_json(response), MAX_JOB_ROWS)

    async def async_list_runnables(
        self, kind: RunnableKind, page: PageRequest
    ) -> tuple[WindmillRunnable, ...]:
        """Return one bounded page of runnable scripts or flows."""
        workspace = quote(self.workspace, safe="")
        segment = "scripts" if kind is RunnableKind.SCRIPT else "flows"
        response = await self._async_get(
            f"/api/w/{workspace}/{segment}/list",
            authenticated=True,
            accept="application/json",
            params=page.as_params(),
        )
        self._raise_for_status(response, not_found=WindmillNotFoundError)
        return self._parse_runnables(kind, self._decode_json(response), page.per_page)

    async def async_get_runnable(self, kind: RunnableKind, path: str) -> RunnableDetails:
        """Read one runnable and project only safe addressing and schema metadata."""
        workspace = quote(self.workspace, safe="")
        safe_path = quote(normalize_runnable_path(path), safe="/")
        endpoint = (
            f"/api/w/{workspace}/scripts/get/p/{safe_path}"
            if kind is RunnableKind.SCRIPT
            else f"/api/w/{workspace}/flows/get/{safe_path}"
        )
        response = await self._async_get(
            endpoint,
            authenticated=True,
            accept="application/json",
        )
        self._raise_for_status(response, not_found=WindmillNotFoundError)
        return self._parse_runnable_details(kind, path, self._decode_json(response))

    async def async_run_runnable(
        self,
        kind: RunnableKind,
        path: str,
        arguments: Mapping[str, Any],
        *,
        script_hash: str | None = None,
        flow_version: int | None = None,
    ) -> str:
        """Start one selected runnable asynchronously and return its job identifier."""
        workspace = quote(self.workspace, safe="")
        safe_path = quote(normalize_runnable_path(path), safe="/")
        if kind is RunnableKind.SCRIPT:
            target = (
                f"/api/w/{workspace}/jobs/run/h/{quote(script_hash, safe='')}"
                if script_hash is not None
                else f"/api/w/{workspace}/jobs/run/p/{safe_path}"
            )
        else:
            target = (
                f"/api/w/{workspace}/jobs/run/fv/{flow_version}"
                if flow_version is not None
                else f"/api/w/{workspace}/jobs/run/f/{safe_path}"
            )

        response = await self._async_post(
            target,
            accept="text/plain",
            json_body=dict(arguments),
        )
        self._raise_for_status(
            response,
            success_statuses=frozenset({200, 201}),
            not_found=WindmillNotFoundError,
        )
        self._require_content_type(response, "text/plain")
        try:
            job_id = response.payload.decode("utf-8").strip().strip('"')
        except UnicodeDecodeError as err:
            raise WindmillProtocolError("Windmill returned an invalid job identifier") from err
        if not _is_uuid(job_id):
            raise WindmillProtocolError("Windmill returned an invalid job identifier")
        return job_id

    async def async_cancel_job(self, job_id: str) -> None:
        """Cancel one job that Home Assistant started and tracked."""
        if not _is_uuid(job_id):
            raise WindmillRequestError("Job identifier is invalid")
        workspace = quote(self.workspace, safe="")
        response = await self._async_post(
            f"/api/w/{workspace}/jobs_u/queue/cancel/{quote(job_id, safe='')}",
            accept="text/plain",
            json_body={"reason": CANCELLATION_REASON},
        )
        self._raise_for_status(
            response,
            success_statuses=frozenset({200, 201, 202}),
            not_found=WindmillNotFoundError,
        )

    async def _async_get_identity(self) -> WindmillIdentity:
        """Validate the token and workspace through the verified whoami endpoint."""
        workspace = quote(self.workspace, safe="")
        response = await self._async_get(
            f"/api/w/{workspace}/users/whoami",
            authenticated=True,
            accept="application/json",
        )
        self._raise_for_status(response, not_found=WindmillWorkspaceError)
        return self._parse_identity(self._decode_json(response))

    async def _probe_json_object(
        self,
        path: str,
        *,
        authenticated: bool = True,
        authentication_required: bool = True,
        body_statuses: frozenset[int] = frozenset({200}),
        scope_denied_statuses: frozenset[int] = frozenset(),
    ) -> CapabilityAvailability:
        """Probe an endpoint whose successful response must be a JSON object."""

        async def validate() -> None:
            response = await self._async_get(
                path,
                authenticated=authenticated,
                accept="application/json",
                body_statuses=body_statuses,
            )
            if response.status in scope_denied_statuses:
                raise WindmillAuthorizationError(
                    "Windmill token scope cannot address this endpoint"
                )
            self._raise_for_status(
                response,
                success_statuses=body_statuses,
                not_found=WindmillNotFoundError,
                authentication_required=authentication_required,
            )
            self._parse_detailed_health(self._decode_json(response))

        return await self._probe(validate())

    async def _probe_json_list(
        self,
        path: str,
        *,
        params: Mapping[str, str | int],
        max_items: int = 1,
        authentication_required: bool = True,
    ) -> CapabilityAvailability:
        """Probe a bounded list endpoint and discard every returned row.

        `max_items` defaults to the requested page size of one row. Only an endpoint that
        does not honour `per_page` for every row it returns may raise it.
        """

        async def validate() -> None:
            response = await self._async_get(
                path,
                authenticated=True,
                accept="application/json",
                params=params,
            )
            self._raise_for_status(
                response,
                not_found=WindmillNotFoundError,
                authentication_required=authentication_required,
            )
            payload = self._decode_json(response)
            if not isinstance(payload, list) or len(payload) > max_items:
                raise WindmillProtocolError("Windmill returned an invalid bounded list")

        return await self._probe(validate())

    @staticmethod
    def _require_context() -> CapabilityAvailability:
        """Never infer a target-specific write permission from a read probe."""
        return CapabilityAvailability(
            CapabilityStatus.NOT_APPLICABLE,
            CapabilityReason.CONTEXT_REQUIRED,
        )

    @staticmethod
    def _parse_runnables(kind: RunnableKind, data: Any, limit: int) -> tuple[WindmillRunnable, ...]:
        """Allowlist kind, path and summary, and drop rows that cannot be run."""
        if not isinstance(data, list) or len(data) > limit:
            raise WindmillProtocolError("Windmill returned an invalid runnable list")
        runnables: list[WindmillRunnable] = []
        for row in data:
            if not isinstance(row, dict):
                raise WindmillProtocolError("Windmill returned an invalid runnable")
            raw_path = row.get("path")
            if not _is_bounded_text(raw_path):
                raise WindmillProtocolError("Windmill returned an invalid runnable path")
            if row.get("archived") is True or row.get("draft_only") is True:
                continue
            try:
                path = normalize_runnable_path(raw_path)
            except WindmillRequestError:
                continue
            summary = row.get("summary")
            runnables.append(
                WindmillRunnable(
                    kind=kind,
                    path=path,
                    summary=summary.strip() if _is_bounded_text(summary) else "",
                )
            )
        return tuple(runnables)

    @classmethod
    def _parse_runnable_details(cls, kind: RunnableKind, path: str, data: Any) -> RunnableDetails:
        """Allowlist addressing metadata and project the input schema safely."""
        if not isinstance(data, dict):
            raise WindmillProtocolError("Windmill returned an invalid runnable")
        summary = data.get("summary")
        script_hash = data.get("hash") if kind is RunnableKind.SCRIPT else None
        if script_hash is not None and not _is_bounded_text(str(script_hash)):
            raise WindmillProtocolError("Windmill returned an invalid script hash")
        # The flow object carries `version_id`, never `version` — the pinned `Flow` schema has
        # no `version` field, confirmed live against Cloud EE v1.779.0 on 2026-08-05. Reading
        # the wrong key silently disabled pinning: `flow_version` stayed `None`, so a flow the
        # user had pinned ran at latest anyway.
        raw_version = data.get("version_id") if kind is RunnableKind.FLOW else None
        # v1.775.2 declares it as a JSON `number`. Deployments send an integer, but an exactly
        # integral float must not silently disable pinning either.
        if isinstance(raw_version, float) and raw_version.is_integer():
            raw_version = int(raw_version)
        flow_version = raw_version if _is_count(raw_version) else None
        parameters, supported, reason = cls._project_schema(data.get("schema"))
        return RunnableDetails(
            kind=kind,
            path=normalize_runnable_path(path),
            summary=summary.strip() if _is_bounded_text(summary) else "",
            script_hash=None if script_hash is None else str(script_hash),
            flow_version=flow_version,
            parameters=parameters,
            schema_supported=supported,
            schema_reason=reason,
        )

    @staticmethod
    def _project_schema(schema: Any) -> tuple[tuple[RunnableParameter, ...], bool, str | None]:
        """Keep parameter name, type, required flag and bounded enum values only."""
        if schema is None:
            return ((), True, None)
        if not isinstance(schema, dict):
            return ((), False, "invalid_schema")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            return ((), False, "invalid_schema")
        if len(properties) > MAX_RUNNABLE_PARAMETERS:
            return ((), False, "too_many_parameters")

        parameters: list[RunnableParameter] = []
        supported = True
        reason: str | None = None
        for name, definition in properties.items():
            if not _is_bounded_text(name) or not isinstance(definition, dict):
                return ((), False, "invalid_schema")
            declared = definition.get("type")
            if declared not in SUPPORTED_PARAMETER_TYPES:
                supported = False
                reason = "unsupported_parameter_type"
                declared = "unknown"
            values = definition.get("enum")
            enum: tuple[str, ...] | None = None
            if isinstance(values, list) and values:
                if len(values) > MAX_ENUM_VALUES or not all(_is_bounded_text(v) for v in values):
                    supported = False
                    reason = reason or "unsupported_enum"
                else:
                    enum = tuple(str(value) for value in values)
            parameters.append(
                RunnableParameter(
                    name=name,
                    type=str(declared),
                    required=name in required,
                    enum=enum,
                )
            )
        return (tuple(parameters), supported, reason)

    @classmethod
    def _parse_jobs(cls, data: Any, limit: int) -> tuple[WindmillJob, ...]:
        """Allowlist bounded job metadata and discard every payload field.

        The page fails closed above `limit` instead of being truncated: the union is not
        globally ordered, so dropping rows would silently drop completions and their events.
        """
        if not isinstance(data, list) or len(data) > limit:
            raise WindmillProtocolError("Windmill returned an invalid job list")
        return tuple(cls._parse_job(row) for row in data)

    @classmethod
    def _parse_job(cls, row: Any) -> WindmillJob:
        """Parse one job row, discriminating queued and completed rows structurally."""
        if not isinstance(row, dict):
            raise WindmillProtocolError("Windmill returned an invalid job")
        identifier = row.get("id")
        kind = row.get("job_kind")
        path = row.get("script_path")
        if not _is_uuid(identifier) or not _is_bounded_text(kind):
            raise WindmillProtocolError("Windmill returned an invalid job")
        if path is not None and not _is_bounded_text(path):
            raise WindmillProtocolError("Windmill returned an invalid job path")
        created_at = cls._parse_timestamp(row.get("created_at"), "job")
        canceled = row.get("canceled", False)
        if not isinstance(canceled, bool):
            raise WindmillProtocolError("Windmill returned an invalid job cancellation flag")

        if "success" in row:
            success = row.get("success")
            if not isinstance(success, bool):
                raise WindmillProtocolError("Windmill returned an invalid job result flag")
            state = (
                JobState.CANCELED
                if canceled
                else (JobState.SUCCESS if success else JobState.FAILURE)
            )
            raw_completed = row.get("completed_at")
            completed_at = (
                None if raw_completed is None else cls._parse_timestamp(raw_completed, "job")
            )
            duration = row.get("duration_ms")
            if duration is not None and not _is_count(duration):
                raise WindmillProtocolError("Windmill returned an invalid job duration")
            return WindmillJob(
                id=str(identifier),
                state=state,
                kind=str(kind).strip(),
                path=None if path is None else str(path).strip(),
                created_at=created_at,
                completed_at=completed_at,
                duration_ms=duration,
            )

        running = row.get("running")
        if not isinstance(running, bool):
            raise WindmillProtocolError("Windmill returned an invalid job")
        raw_scheduled = row.get("scheduled_for")
        return WindmillJob(
            id=str(identifier),
            state=JobState.RUNNING if running else JobState.QUEUED,
            kind=str(kind).strip(),
            path=None if path is None else str(path).strip(),
            created_at=created_at,
            completed_at=None,
            duration_ms=None,
            scheduled_for=(
                None if raw_scheduled is None else cls._parse_timestamp(raw_scheduled, "job")
            ),
        )

    @staticmethod
    def _parse_identity(data: Any) -> WindmillIdentity:
        """Allowlist and validate the bounded whoami response."""
        if not isinstance(data, dict):
            raise WindmillProtocolError("Windmill returned an invalid identity")
        username = data.get("username")
        is_admin = data.get("is_admin", False)
        is_super_admin = data.get("is_super_admin", False)
        if not _is_bounded_text(username):
            raise WindmillProtocolError("Windmill returned an invalid identity")
        if not isinstance(is_admin, bool) or not isinstance(is_super_admin, bool):
            raise WindmillProtocolError("Windmill returned invalid role fields")
        return WindmillIdentity(
            username=username.strip(),
            is_admin=is_admin,
            is_super_admin=is_super_admin,
        )
