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

import aiohttp

from .const import DEFAULT_CONNECT_TIMEOUT, DEFAULT_REQUEST_TIMEOUT, MAX_RESPONSE_BYTES

MAX_PAGE_SIZE = 100
MAX_RETRY_AFTER = 300.0
MAX_WORKSPACE_ROWS = 200
MAX_WORKER_GROUP_ROWS = 200
MAX_TEXT_FIELD_LENGTH = 256
ALIVE_WORKER_SECONDS = 300


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


def _is_bounded_text(value: Any) -> TypeIs[str]:
    """Return whether an untrusted value is a short non-empty string."""
    return isinstance(value, str) and bool(value.strip()) and len(value) <= MAX_TEXT_FIELD_LENGTH


def _is_count(value: Any) -> TypeIs[int]:
    """Return whether an untrusted value is a non-negative integer count."""
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def normalize_base_url(value: str) -> str:
    """Normalize and validate a Windmill base URL without weakening TLS."""
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
    if scheme == "http" and not _is_loopback(host):
        raise WindmillUrlError("Remote Windmill instances must use HTTPS")

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
        """Return the bounded set of workspaces visible to the configured token."""
        response = await self._async_get(
            "/api/workspaces/list",
            authenticated=True,
            accept="application/json",
        )
        self._raise_for_status(response, not_found=WindmillNotFoundError)
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
        if not path.startswith("/") or "?" in path or "#" in path:
            raise WindmillProtocolError("Windmill client path is invalid")
        headers = {"Accept": accept}
        if authenticated:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with self._session.get(
                f"{self.base_url}{path}",
                headers=headers,
                params=params,
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
        """Map HTTP statuses to the stable typed client taxonomy."""
        status = response.status
        if status in success_statuses:
            return
        if status == 401:
            if authentication_required:
                raise WindmillAuthenticationError("Windmill rejected the token")
            raise WindmillAuthorizationError("Windmill denied the public probe")
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
                    body_statuses=frozenset({200, 503}),
                )
            ),
            asyncio.create_task(
                self._probe_json_list(
                    "/api/workers/list",
                    params={**page.as_params(), "ping_since": 300},
                )
            ),
            asyncio.create_task(
                self._probe_json_list(
                    f"/api/w/{workspace}/jobs/list",
                    params=runs_params,
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
        body_statuses: frozenset[int] = frozenset({200}),
    ) -> CapabilityAvailability:
        """Probe an endpoint whose successful response must be a JSON object."""

        async def validate() -> None:
            response = await self._async_get(
                path,
                authenticated=authenticated,
                accept="application/json",
                body_statuses=body_statuses,
            )
            self._raise_for_status(
                response,
                success_statuses=body_statuses,
                not_found=WindmillNotFoundError,
            )
            self._parse_detailed_health(self._decode_json(response))

        return await self._probe(validate())

    async def _probe_json_list(
        self,
        path: str,
        *,
        params: Mapping[str, str | int],
    ) -> CapabilityAvailability:
        """Probe a bounded list endpoint and discard every returned row."""

        async def validate() -> None:
            response = await self._async_get(
                path,
                authenticated=True,
                accept="application/json",
                params=params,
            )
            self._raise_for_status(response, not_found=WindmillNotFoundError)
            payload = self._decode_json(response)
            if not isinstance(payload, list) or len(payload) > 1:
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
