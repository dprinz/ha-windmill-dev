"""Tests for the independent asynchronous Windmill API client."""

import asyncio
import json
from datetime import UTC, datetime
from http import HTTPStatus

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.windmill.api import (
    JobState,
    PageRequest,
    RunnableKind,
    RunnableParameter,
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillClient,
    WindmillConflictError,
    WindmillConnectionError,
    WindmillEdition,
    WindmillHealthState,
    WindmillInstanceClient,
    WindmillNotFoundError,
    WindmillProtocolError,
    WindmillRateLimitError,
    WindmillRequestError,
    WindmillRunnable,
    WindmillServerError,
    WindmillTimeoutError,
    WindmillUrlError,
    WindmillWorker,
    WindmillWorkspaceError,
    WindmillWorkspaceInfo,
    normalize_base_url,
    normalize_runnable_path,
    normalize_workspace,
)
from custom_components.windmill.const import MAX_RESPONSE_BYTES

BASE_URL = "https://windmill.example"
WORKSPACE = "home-assistant"
VERSION_URL = f"{BASE_URL}/api/version"
HEALTH_URL = f"{BASE_URL}/api/health/status?force=false"
WHOAMI_URL = f"{BASE_URL}/api/w/{WORKSPACE}/users/whoami"
WORKSPACES_URL = f"{BASE_URL}/api/workspaces/list"
TOKEN = "obviously-fake-test-token"
JSON_HEADERS = {"Content-Type": "application/json"}
TEXT_HEADERS = {"Content-Type": "text/plain"}
HEALTH_BODY = {
    "status": "healthy",
    "checked_at": "2026-08-02T10:00:00Z",
    "database_healthy": True,
    "workers_alive": 2,
}


@pytest.fixture
def version_mock(aioclient_mock: object) -> None:
    """Expose a valid public Windmill version probe."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        VERSION_URL,
        text="CE 1.775.2",
        headers=TEXT_HEADERS,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" HTTPS://Windmill.Example:443/ ", BASE_URL),
        ("https://windmill.example/root/", f"{BASE_URL}/root"),
        ("https://windmill.example/%72oot/caf%C3%A9", f"{BASE_URL}/root/caf%C3%A9"),
        ("http://localhost:8000/", "http://localhost:8000"),
        ("http://[::1]:8000/", "http://[::1]:8000"),
    ],
)
def test_normalize_base_url(value: str, expected: str) -> None:
    """Base URLs are canonicalized without changing their deployment path."""
    assert normalize_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "windmill.example",
        "ftp://windmill.example",
        "http://windmill.example",
        "https://user:secret@windmill.example",
        "https://windmill.example?token=secret",
        "https://windmill.example/#fragment",
        "https://windmill.example/root/../admin",
        "https://windmill.example/root/%2e%2e/admin",
        "https://windmill.example/root/%2F/admin",
        "https://windmill.example/root/%5c/admin",
        "https://windmill.example:99999",
        "https://./",
        "https://\ud800.example",
    ],
)
def test_reject_unsafe_base_url(value: str) -> None:
    """Unsafe or ambiguous base URLs are rejected before any request."""
    with pytest.raises(WindmillUrlError):
        normalize_base_url(value)


def test_normalize_workspace() -> None:
    """Workspace storage is trimmed and bounded."""
    assert normalize_workspace("  home-assistant  ") == WORKSPACE
    with pytest.raises(WindmillWorkspaceError):
        normalize_workspace("\x00")
    with pytest.raises(WindmillWorkspaceError):
        normalize_workspace(42)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("page", "per_page"),
    [(0, 1), (True, 1), (1, 0), (1, 101), (1, False), ("1", 1)],
)
def test_page_request_is_bounded(page: object, per_page: object) -> None:
    """Pagination never permits zero, negative or oversized page requests."""
    with pytest.raises(ValueError):
        PageRequest(page=page, per_page=per_page)  # type: ignore[arg-type]

    assert PageRequest(page=2, per_page=100).as_params() == {"page": 2, "per_page": 100}


async def test_token_is_required(hass: HomeAssistant) -> None:
    """A client cannot be created without authorization material."""
    with pytest.raises(WindmillAuthenticationError):
        WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, "")


async def test_validate_identity_and_authorization_header(
    hass: HomeAssistant, aioclient_mock: object, version_mock: None
) -> None:
    """Validation calls whoami and retains only allowlisted identity fields."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        WHOAMI_URL,
        json={
            "username": "automation",
            "is_admin": False,
            "is_super_admin": False,
            "email": "must-not-be-retained@example.invalid",
        },
        headers=JSON_HEADERS,
    )
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    connection = await client.async_connect()
    identity = connection.identity

    assert identity.username == "automation"
    assert identity.is_admin is False
    assert connection.server.edition is WindmillEdition.COMMUNITY
    assert connection.server.version == "1.775.2"
    assert not hasattr(identity, "email")
    assert client.identity_key == (BASE_URL, WORKSPACE)
    calls = aioclient_mock.mock_calls  # type: ignore[attr-defined]
    assert "Authorization" not in calls[0][3]
    assert calls[1][3]["Authorization"] == f"Bearer {TOKEN}"
    assert all("token=" not in str(call[1]) for call in calls)


@pytest.mark.parametrize(
    ("status", "exception_type"),
    [
        (HTTPStatus.UNAUTHORIZED, WindmillAuthenticationError),
        (HTTPStatus.FORBIDDEN, WindmillAuthorizationError),
        (HTTPStatus.NOT_FOUND, WindmillWorkspaceError),
        (HTTPStatus.BAD_REQUEST, WindmillRequestError),
        (HTTPStatus.CONFLICT, WindmillConflictError),
        (HTTPStatus.TOO_MANY_REQUESTS, WindmillRateLimitError),
        (HTTPStatus.SERVICE_UNAVAILABLE, WindmillServerError),
        (HTTPStatus.FOUND, WindmillProtocolError),
    ],
)
async def test_status_error_mapping(
    hass: HomeAssistant,
    aioclient_mock: object,
    version_mock: None,
    status: HTTPStatus,
    exception_type: type[Exception],
) -> None:
    """HTTP statuses map to stable typed errors without response bodies."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        WHOAMI_URL,
        status=status,
        text=f"untrusted-{TOKEN}",
        headers=JSON_HEADERS,
    )
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(exception_type) as caught:
        await client.async_validate()

    assert TOKEN not in str(caught.value)


@pytest.mark.parametrize(
    ("response", "headers"),
    [
        ("not-json", JSON_HEADERS),
        ("[]", JSON_HEADERS),
        ('{"username": 42}', JSON_HEADERS),
        ('{"username": "user", "is_admin": "yes"}', JSON_HEADERS),
        ('{"username": "user"}', {"Content-Type": "text/plain"}),
    ],
)
async def test_protocol_error_mapping(
    hass: HomeAssistant,
    aioclient_mock: object,
    version_mock: None,
    response: str,
    headers: dict[str, str],
) -> None:
    """Malformed or unexpected identity responses fail closed."""
    aioclient_mock.get(WHOAMI_URL, text=response, headers=headers)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_validate()


@pytest.mark.parametrize(
    ("error", "exception_type"),
    [
        (TimeoutError(), WindmillTimeoutError),
        (aiohttp.ClientConnectionError(), WindmillConnectionError),
    ],
)
async def test_transport_error_mapping(
    hass: HomeAssistant,
    aioclient_mock: object,
    version_mock: None,
    error: Exception,
    exception_type: type[Exception],
) -> None:
    """Timeout and connection failures remain distinct typed errors."""
    aioclient_mock.get(WHOAMI_URL, exc=error)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(exception_type):
        await client.async_validate()


async def test_response_size_is_bounded(
    hass: HomeAssistant, aioclient_mock: object, version_mock: None
) -> None:
    """Large upstream responses are rejected before parsing or retention."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        WHOAMI_URL,
        text="{}",
        headers={"Content-Type": "application/json", "Content-Length": "70000"},
    )
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_validate()


async def test_chunked_response_is_read_to_eof_with_hard_limit() -> None:
    """A valid first chunk cannot hide an oversized delayed response tail."""

    class ChunkedContent:
        def __init__(self) -> None:
            self._chunks = [
                json.dumps(HEALTH_BODY).encode(),
                b" " * MAX_RESPONSE_BYTES,
            ]

        async def read(self, size: int) -> bytes:
            await asyncio.sleep(0)
            if not self._chunks:
                return b""
            chunk = self._chunks[0]
            result = chunk[:size]
            if len(result) == len(chunk):
                self._chunks.pop(0)
            else:
                self._chunks[0] = chunk[size:]
            return result

    class Response:
        status = HTTPStatus.OK
        headers = JSON_HEADERS
        content = ChunkedContent()

        async def __aenter__(self) -> Response:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    class Session:
        def get(self, *args: object, **kwargs: object) -> Response:
            return Response()

    client = WindmillClient(Session(), BASE_URL, WORKSPACE, TOKEN)  # type: ignore[arg-type]

    with pytest.raises(WindmillProtocolError, match="too large"):
        await client.async_get_health_status()


@pytest.mark.parametrize(
    ("body", "content_length"),
    [
        ("{}", "invalid"),
        ("{}", "-1"),
        (" " * 65_537, None),
    ],
)
async def test_invalid_or_unbounded_response_length(
    hass: HomeAssistant,
    aioclient_mock: object,
    version_mock: None,
    body: str,
    content_length: str | None,
) -> None:
    """Invalid length metadata and oversized chunked bodies fail closed."""
    headers = {"Content-Type": "application/json"}
    if content_length is not None:
        headers["Content-Length"] = content_length
    aioclient_mock.get(WHOAMI_URL, text=body, headers=headers)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_validate()


@pytest.mark.parametrize(
    ("status", "exception_type"),
    [
        (HTTPStatus.UNAUTHORIZED, WindmillProtocolError),
        (HTTPStatus.NOT_FOUND, WindmillProtocolError),
        (HTTPStatus.TOO_MANY_REQUESTS, WindmillRateLimitError),
        (HTTPStatus.SERVICE_UNAVAILABLE, WindmillServerError),
    ],
)
async def test_version_probe_failure_mapping(
    hass: HomeAssistant,
    aioclient_mock: object,
    status: HTTPStatus,
    exception_type: type[Exception],
) -> None:
    """A base deployment failure is not misreported as a workspace failure."""
    aioclient_mock.get(VERSION_URL, status=status)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(exception_type):
        await client.async_validate()

    calls = aioclient_mock.mock_calls  # type: ignore[attr-defined]
    assert len(calls) == 1
    assert "Authorization" not in calls[0][3]


@pytest.mark.parametrize(
    ("text", "headers"),
    [
        ("not-windmill", TEXT_HEADERS),
        ("CE 1.775.2", JSON_HEADERS),
    ],
)
async def test_version_probe_validates_contract(
    hass: HomeAssistant,
    aioclient_mock: object,
    text: str,
    headers: dict[str, str],
) -> None:
    """The public probe must look like the verified Windmill version endpoint."""
    aioclient_mock.get(VERSION_URL, text=text, headers=headers)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_validate()


@pytest.mark.parametrize("status", [HTTPStatus.OK, HTTPStatus.SERVICE_UNAVAILABLE])
async def test_health_status_parsing(
    hass: HomeAssistant,
    aioclient_mock: object,
    status: HTTPStatus,
) -> None:
    """Healthy and unhealthy HTTP statuses share one bounded health model."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        HEALTH_URL,
        status=status,
        json={
            "status": "healthy" if status == 200 else "unhealthy",
            "checked_at": "2026-08-02T10:00:00Z",
            "database_healthy": status == 200,
            "workers_alive": 2 if status == 200 else 0,
            "secret": f"untrusted-{TOKEN}",
        },
        headers=JSON_HEADERS,
    )
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    health = await client.async_get_health_status()

    expected = WindmillHealthState.HEALTHY if status == 200 else WindmillHealthState.UNHEALTHY
    assert health.status is expected
    assert health.checked_at.isoformat() == "2026-08-02T10:00:00+00:00"
    assert health.workers_alive in {0, 2}
    assert TOKEN not in repr(health)
    call = aioclient_mock.mock_calls[0]  # type: ignore[attr-defined]
    assert "Authorization" not in call[3]


@pytest.mark.parametrize(
    "body",
    [
        [],
        {**{"checked_at": "now", "database_healthy": True, "workers_alive": 1}},
        {**HEALTH_BODY, "status": "mystery"},
        {**HEALTH_BODY, "checked_at": ""},
        {**HEALTH_BODY, "checked_at": "not-a-time"},
        {**HEALTH_BODY, "checked_at": "2026-08-02T10:00:00"},
        {**HEALTH_BODY, "database_healthy": "yes"},
        {**HEALTH_BODY, "workers_alive": True},
        {**HEALTH_BODY, "workers_alive": -1},
    ],
)
async def test_health_status_rejects_invalid_models(
    hass: HomeAssistant,
    aioclient_mock: object,
    body: object,
) -> None:
    """Malformed health fields fail closed without retaining upstream data."""
    aioclient_mock.get(HEALTH_URL, json=body, headers=JSON_HEADERS)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_get_health_status()


async def test_retry_after_is_bounded(
    hass: HomeAssistant, aioclient_mock: object, version_mock: None
) -> None:
    """Only bounded delta-seconds survive a rate-limit response."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        WHOAMI_URL,
        status=HTTPStatus.TOO_MANY_REQUESTS,
        headers={"Retry-After": "120"},
    )
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(WindmillRateLimitError) as caught:
        await client.async_validate()

    assert caught.value.retry_after == 120


async def test_workspace_listing_allowlists_bounded_fields(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """Workspace listing keeps only the bounded identifier and label."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        WORKSPACES_URL,
        json=[
            {
                "id": WORKSPACE,
                "name": "Home Assistant",
                "owner": "must-not-be-retained@example.invalid",
            },
            {"id": "admin"},
        ],
        headers=JSON_HEADERS,
    )
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    workspaces = await client.async_list_workspaces()

    assert workspaces == (
        WindmillWorkspaceInfo(id=WORKSPACE, name="Home Assistant"),
        WindmillWorkspaceInfo(id="admin", name="admin"),
    )
    call = aioclient_mock.mock_calls[0]  # type: ignore[attr-defined]
    assert call[3]["Authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize(
    "body",
    [
        {"id": WORKSPACE},
        ["home-assistant"],
        [{"id": ""}],
        [{"id": WORKSPACE, "name": 42}],
        [{"id": "x" * 257}],
        [{"id": WORKSPACE}] * 201,
    ],
)
async def test_workspace_listing_rejects_invalid_models(
    hass: HomeAssistant, aioclient_mock: object, body: object
) -> None:
    """A malformed workspace list fails closed without retaining upstream data."""
    aioclient_mock.get(WORKSPACES_URL, json=body, headers=JSON_HEADERS)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_list_workspaces()


@pytest.mark.parametrize(
    ("status", "exception_type"),
    [
        (HTTPStatus.UNAUTHORIZED, WindmillAuthenticationError),
        (HTTPStatus.FORBIDDEN, WindmillAuthorizationError),
        (HTTPStatus.NOT_FOUND, WindmillNotFoundError),
        (HTTPStatus.SERVICE_UNAVAILABLE, WindmillServerError),
    ],
)
async def test_workspace_listing_status_mapping(
    hass: HomeAssistant,
    aioclient_mock: object,
    status: HTTPStatus,
    exception_type: type[Exception],
) -> None:
    """Workspace listing keeps authentication, permission and server failures distinct."""
    aioclient_mock.get(WORKSPACES_URL, status=status)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    with pytest.raises(exception_type):
        await client.async_list_workspaces()


DETAILED_URL = f"{BASE_URL}/api/health/detailed"
DETAILED_BODY = {
    "status": "degraded",
    "checked_at": "2026-08-02T10:00:00Z",
    "version": "CE 1.775.2",
    "checks": {
        "database": {"healthy": True, "latency_ms": 3, "pool": {"size": 4, "idle": 2}},
        "workers": {"healthy": True, "active_count": 2, "versions": ["1.775.2"]},
        "queue": {"pending_jobs": 3, "running_jobs": 1},
        "readiness": {"healthy": True},
    },
}


async def test_detailed_health_allowlists_bounded_fields(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """Detailed health keeps five bounded facts and discards everything else."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        DETAILED_URL,
        json=DETAILED_BODY,
        headers=JSON_HEADERS,
    )
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    detailed = await client.async_get_detailed_health()

    assert detailed.status is WindmillHealthState.DEGRADED
    assert detailed.database_healthy is True
    assert detailed.workers_alive == 2
    assert detailed.pending_jobs == 3
    assert detailed.running_jobs == 1
    assert not hasattr(detailed, "version")
    call = aioclient_mock.mock_calls[0]  # type: ignore[attr-defined]
    assert call[3]["Authorization"] == f"Bearer {TOKEN}"


async def test_detailed_health_accepts_null_optional_checks(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """Nullable worker and queue checks become unknown counts, not failures."""
    body = {
        **DETAILED_BODY,
        "status": "unhealthy",
        "checks": {"database": {"healthy": False}, "workers": None, "queue": None},
    }
    aioclient_mock.get(DETAILED_URL, json=body, headers=JSON_HEADERS, status=503)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    detailed = await client.async_get_detailed_health()

    assert detailed.status is WindmillHealthState.UNHEALTHY
    assert detailed.database_healthy is False
    assert detailed.workers_alive is None
    assert detailed.pending_jobs is None
    assert detailed.running_jobs is None


@pytest.mark.parametrize(
    "body",
    [
        [],
        {**DETAILED_BODY, "status": "mystery"},
        {**DETAILED_BODY, "checked_at": "not-a-time"},
        {**DETAILED_BODY, "version": ""},
        {**DETAILED_BODY, "checks": {}},
        {**DETAILED_BODY, "checks": {"database": {"healthy": "yes"}}},
        {**DETAILED_BODY, "checks": {"database": {"healthy": True}, "queue": []}},
        {
            **DETAILED_BODY,
            "checks": {"database": {"healthy": True}, "queue": {"pending_jobs": -1}},
        },
        {
            **DETAILED_BODY,
            "checks": {"database": {"healthy": True}, "workers": {"active_count": True}},
        },
    ],
)
async def test_detailed_health_rejects_invalid_models(
    hass: HomeAssistant, aioclient_mock: object, body: object
) -> None:
    """A malformed detailed health response fails closed."""
    aioclient_mock.get(DETAILED_URL, json=body, headers=JSON_HEADERS)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_get_detailed_health()


@pytest.mark.parametrize(
    ("status", "exception_type"),
    [
        (HTTPStatus.UNAUTHORIZED, WindmillAuthenticationError),
        (HTTPStatus.FORBIDDEN, WindmillAuthorizationError),
        (HTTPStatus.NOT_FOUND, WindmillNotFoundError),
    ],
)
async def test_detailed_health_status_mapping(
    hass: HomeAssistant,
    aioclient_mock: object,
    status: HTTPStatus,
    exception_type: type[Exception],
) -> None:
    """Detailed health keeps authentication and permission failures distinct."""
    aioclient_mock.get(DETAILED_URL, status=status)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    with pytest.raises(exception_type):
        await client.async_get_detailed_health()


WORKERS_URL = f"{BASE_URL}/api/workers/list?page=1&per_page=2&ping_since=300"
WORKER_GROUPS_URL = f"{BASE_URL}/api/configs/list_worker_groups"
WORKER_ROW = {
    "worker": "wk-default-host1-abc",
    "worker_instance": "host1",
    "worker_group": "default",
    "wm_version": "1.775.2",
    "ip": "10.0.0.5",
    "last_job_id": "00000000-0000-4000-8000-000000000001",
    "last_job_workspace_id": "secret-workspace",
    "custom_tags": ["deno"],
    "jobs_executed": 42,
}


async def test_worker_listing_discards_sensitive_fields(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """Worker rows keep four bounded fields and drop every denylisted value."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        WORKERS_URL,
        json=[WORKER_ROW],
        headers=JSON_HEADERS,
    )
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    workers = await client.async_list_workers(PageRequest(page=1, per_page=2))

    assert workers == (
        WindmillWorker(
            name="wk-default-host1-abc",
            instance="host1",
            group="default",
            version="1.775.2",
        ),
    )
    assert "10.0.0.5" not in repr(workers)
    assert "secret-workspace" not in repr(workers)
    assert "deno" not in repr(workers)
    call = aioclient_mock.mock_calls[0]  # type: ignore[attr-defined]
    assert call[3]["Authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize(
    "body",
    [
        {"worker": "wk"},
        ["wk-default"],
        [{**WORKER_ROW, "worker": ""}],
        [{**WORKER_ROW, "worker_instance": 42}],
        [{**WORKER_ROW, "worker_group": None}],
        [{**WORKER_ROW, "wm_version": "x" * 257}],
        [WORKER_ROW, WORKER_ROW, WORKER_ROW],
    ],
)
async def test_worker_listing_rejects_invalid_models(
    hass: HomeAssistant, aioclient_mock: object, body: object
) -> None:
    """A malformed or oversized worker page fails closed."""
    aioclient_mock.get(WORKERS_URL, json=body, headers=JSON_HEADERS)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_list_workers(PageRequest(page=1, per_page=2))


async def test_worker_group_listing_keeps_names_only(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """Worker-group listing keeps unique names and discards their configuration."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        WORKER_GROUPS_URL,
        json=[
            {"name": "default", "config": {"init_bash": "must-not-be-retained"}},
            {"name": "gpu"},
            {"name": "default"},
        ],
        headers=JSON_HEADERS,
    )
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    groups = await client.async_list_worker_groups()

    assert groups == ("default", "gpu")
    assert "must-not-be-retained" not in repr(groups)


@pytest.mark.parametrize(
    "body",
    [{"name": "default"}, ["default"], [{"config": {}}], [{"name": ""}]],
)
async def test_worker_group_listing_rejects_invalid_models(
    hass: HomeAssistant, aioclient_mock: object, body: object
) -> None:
    """A malformed worker-group listing fails closed."""
    aioclient_mock.get(WORKER_GROUPS_URL, json=body, headers=JSON_HEADERS)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_list_worker_groups()


@pytest.mark.parametrize(
    ("status", "exception_type"),
    [
        (HTTPStatus.UNAUTHORIZED, WindmillAuthenticationError),
        (HTTPStatus.FORBIDDEN, WindmillAuthorizationError),
        (HTTPStatus.NOT_FOUND, WindmillNotFoundError),
    ],
)
async def test_worker_reads_keep_failures_distinct(
    hass: HomeAssistant,
    aioclient_mock: object,
    status: HTTPStatus,
    exception_type: type[Exception],
) -> None:
    """Worker and worker-group reads map statuses to the shared taxonomy."""
    aioclient_mock.get(WORKERS_URL, status=status)  # type: ignore[attr-defined]
    aioclient_mock.get(WORKER_GROUPS_URL, status=status)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    with pytest.raises(exception_type):
        await client.async_list_workers(PageRequest(page=1, per_page=2))
    with pytest.raises(exception_type):
        await client.async_list_worker_groups()


JOBS_URL = (
    f"{BASE_URL}/api/w/{WORKSPACE}/jobs/list"
    "?page=1&per_page=2&has_null_parent=true&is_flow_step=false"
)
COMPLETED_ROW = {
    "type": "CompletedJob",
    "id": "00000000-0000-4000-8000-000000000002",
    "created_at": "2026-08-02T10:00:00Z",
    "started_at": "2026-08-02T10:00:01Z",
    "completed_at": "2026-08-02T10:01:00Z",
    "duration_ms": 59000,
    "success": False,
    "canceled": False,
    "job_kind": "flow",
    "script_path": "f/example/night",
    "args": {"secret": "must-not-be-retained"},
    "result": {"token": "must-not-be-retained"},
    "logs": "must-not-be-retained",
    "email": "must-not-be-retained@example.invalid",
    "permissioned_as": "u/example",
    "tag": "flow",
}
QUEUED_ROW = {
    "type": "QueuedJob",
    "id": "00000000-0000-4000-8000-000000000001",
    "created_at": "2026-08-02T10:00:00Z",
    "running": True,
    "canceled": False,
    "job_kind": "script",
    "script_path": "u/example/lights",
    "args": {"secret": "must-not-be-retained"},
}


async def test_job_listing_keeps_metadata_and_drops_payloads(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """Job rows keep bounded metadata and never retain arguments, results or logs."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        JOBS_URL,
        json=[QUEUED_ROW, COMPLETED_ROW],
        headers=JSON_HEADERS,
    )
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    jobs = await client.async_list_jobs(PageRequest(page=1, per_page=2))

    assert [job.state for job in jobs] == [JobState.RUNNING, JobState.FAILURE]
    assert jobs[1].completed_at == datetime(2026, 8, 2, 10, 1, tzinfo=UTC)
    assert jobs[1].duration_ms == 59000
    assert jobs[1].path == "f/example/night"
    assert "must-not-be-retained" not in repr(jobs)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({**QUEUED_ROW, "running": False}, JobState.QUEUED),
        ({**COMPLETED_ROW, "success": True}, JobState.SUCCESS),
        ({**COMPLETED_ROW, "success": True, "canceled": True}, JobState.CANCELED),
        ({**COMPLETED_ROW, "completed_at": None}, JobState.FAILURE),
    ],
)
async def test_job_state_mapping(
    hass: HomeAssistant, aioclient_mock: object, row: dict, expected: JobState
) -> None:
    """Queued, running, successful, failed and canceled rows map to bounded states."""
    aioclient_mock.get(JOBS_URL, json=[row], headers=JSON_HEADERS)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    jobs = await client.async_list_jobs(PageRequest(page=1, per_page=2))

    assert jobs[0].state is expected


@pytest.mark.parametrize(
    "body",
    [
        {"id": "00000000-0000-4000-8000-000000000001"},
        ["job"],
        [{**QUEUED_ROW, "id": "not-a-uuid"}],
        [{**QUEUED_ROW, "job_kind": ""}],
        [{**QUEUED_ROW, "script_path": 42}],
        [{**QUEUED_ROW, "created_at": "not-a-time"}],
        [{**QUEUED_ROW, "running": "yes"}],
        [{**QUEUED_ROW, "canceled": "no"}],
        [{**COMPLETED_ROW, "success": "yes"}],
        [{**COMPLETED_ROW, "duration_ms": -1}],
        [QUEUED_ROW, COMPLETED_ROW, QUEUED_ROW],
    ],
)
async def test_job_listing_rejects_invalid_models(
    hass: HomeAssistant, aioclient_mock: object, body: object
) -> None:
    """A malformed or oversized job page fails closed."""
    aioclient_mock.get(JOBS_URL, json=body, headers=JSON_HEADERS)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_list_jobs(PageRequest(page=1, per_page=2))


@pytest.mark.parametrize(
    ("status", "exception_type"),
    [
        (HTTPStatus.UNAUTHORIZED, WindmillAuthenticationError),
        (HTTPStatus.FORBIDDEN, WindmillAuthorizationError),
        (HTTPStatus.TOO_MANY_REQUESTS, WindmillRateLimitError),
    ],
)
async def test_job_listing_status_mapping(
    hass: HomeAssistant,
    aioclient_mock: object,
    status: HTTPStatus,
    exception_type: type[Exception],
) -> None:
    """Job listing keeps authentication, permission and rate-limit failures distinct."""
    aioclient_mock.get(JOBS_URL, status=status)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(exception_type):
        await client.async_list_jobs(PageRequest(page=1, per_page=2))


SCRIPTS_URL = f"{BASE_URL}/api/w/{WORKSPACE}/scripts/list?page=1&per_page=2"
FLOWS_URL = f"{BASE_URL}/api/w/{WORKSPACE}/flows/list?page=1&per_page=2"
SCRIPT_DETAIL_URL = f"{BASE_URL}/api/w/{WORKSPACE}/scripts/get/p/u/automation/lights"
FLOW_DETAIL_URL = f"{BASE_URL}/api/w/{WORKSPACE}/flows/get/f/home/night"
SCRIPT_ROW = {
    "path": "u/automation/lights",
    "summary": "Toggle the lights",
    "hash": "0123456789abcdef",
    "archived": False,
    "language": "python3",
    "extra_perms": {"u/admin": True},
}
SCRIPT_DETAIL = {
    **SCRIPT_ROW,
    "content": "must-not-be-retained",
    "lock": "must-not-be-retained",
    "schema": {
        "type": "object",
        "properties": {
            "room": {"type": "string", "enum": ["kitchen", "hall"], "default": "kitchen"},
            "bright": {"type": "boolean", "description": "must-not-be-retained"},
        },
        "required": ["room"],
    },
}


@pytest.mark.parametrize(
    "value",
    ["", "/", "..", "u/../admin", "u/a b/c", "u/a\\x00/c", "u//c", "x" * 300],
)
def test_runnable_paths_are_validated(value: str) -> None:
    """Unsafe runnable paths are rejected before a URL is built."""
    with pytest.raises(WindmillRequestError):
        normalize_runnable_path(value)

    assert normalize_runnable_path(" u/automation/lights/ ") == "u/automation/lights"


async def test_runnable_listing_projects_safe_metadata(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """Listing keeps kind, path and summary and drops archived or draft rows."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        SCRIPTS_URL,
        json=[
            SCRIPT_ROW,
            {**SCRIPT_ROW, "path": "u/old/script", "archived": True},
        ],
        headers=JSON_HEADERS,
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        FLOWS_URL,
        json=[{"path": "f/home/night", "summary": "", "draft_only": True}],
        headers=JSON_HEADERS,
    )
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    scripts = await client.async_list_runnables(RunnableKind.SCRIPT, PageRequest(1, 2))
    flows = await client.async_list_runnables(RunnableKind.FLOW, PageRequest(1, 2))

    assert scripts == (
        WindmillRunnable(
            kind=RunnableKind.SCRIPT, path="u/automation/lights", summary="Toggle the lights"
        ),
    )
    assert flows == ()
    assert "u/admin" not in repr(scripts)


async def test_runnable_details_project_schema_safely(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """Details keep the hash and a bounded parameter projection only."""
    aioclient_mock.get(SCRIPT_DETAIL_URL, json=SCRIPT_DETAIL, headers=JSON_HEADERS)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    details = await client.async_get_runnable(RunnableKind.SCRIPT, "u/automation/lights")

    assert details.script_hash == "0123456789abcdef"
    assert details.schema_supported is True
    assert details.parameters == (
        RunnableParameter(name="room", type="string", required=True, enum=("kitchen", "hall")),
        RunnableParameter(name="bright", type="boolean", required=False),
    )
    assert "must-not-be-retained" not in repr(details)


async def test_flow_details_use_version_when_present(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """A flow keeps its numeric version when the deployment exposes one."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        FLOW_DETAIL_URL,
        json={"path": "f/home/night", "summary": "Night", "version": 7, "schema": None},
        headers=JSON_HEADERS,
    )
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    details = await client.async_get_runnable(RunnableKind.FLOW, "f/home/night")

    assert details.flow_version == 7
    assert details.script_hash is None
    assert details.schema_supported is True


@pytest.mark.parametrize(
    ("schema", "reason"),
    [
        ("not-a-schema", "invalid_schema"),
        ({"type": "object", "properties": []}, "invalid_schema"),
        ({"type": "object", "properties": {"a": {"$ref": "#/x"}}}, "unsupported_parameter_type"),
        ({"type": "object", "properties": {"a": {"type": "null"}}}, "unsupported_parameter_type"),
        (
            {"type": "object", "properties": {"a": {"type": "string", "enum": [1, 2]}}},
            "unsupported_enum",
        ),
        (
            {
                "type": "object",
                "properties": {f"p{i}": {"type": "string"} for i in range(51)},
            },
            "too_many_parameters",
        ),
    ],
)
async def test_unsupported_schemas_are_flagged(
    hass: HomeAssistant, aioclient_mock: object, schema: object, reason: str
) -> None:
    """An unsupported argument schema is reported before execution is enabled."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        SCRIPT_DETAIL_URL,
        json={**SCRIPT_DETAIL, "schema": schema},
        headers=JSON_HEADERS,
    )
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    details = await client.async_get_runnable(RunnableKind.SCRIPT, "u/automation/lights")

    assert details.schema_supported is False
    assert details.schema_reason == reason


RUN_SCRIPT_URL = f"{BASE_URL}/api/w/{WORKSPACE}/jobs/run/p/u/automation/lights"
RUN_HASH_URL = f"{BASE_URL}/api/w/{WORKSPACE}/jobs/run/h/0123456789abcdef"
RUN_FLOW_URL = f"{BASE_URL}/api/w/{WORKSPACE}/jobs/run/f/f/home/night"
RUN_VERSION_URL = f"{BASE_URL}/api/w/{WORKSPACE}/jobs/run/fv/7"
JOB_UUID = "00000000-0000-4000-8000-00000000000a"


@pytest.mark.parametrize(
    ("kind", "kwargs", "url"),
    [
        (RunnableKind.SCRIPT, {}, RUN_SCRIPT_URL),
        (RunnableKind.SCRIPT, {"script_hash": "0123456789abcdef"}, RUN_HASH_URL),
        (RunnableKind.FLOW, {}, RUN_FLOW_URL),
        (RunnableKind.FLOW, {"flow_version": 7}, RUN_VERSION_URL),
    ],
)
async def test_execution_addresses_the_selected_target(
    hass: HomeAssistant,
    aioclient_mock: object,
    kind: RunnableKind,
    kwargs: dict[str, object],
    url: str,
) -> None:
    """Latest and pinned addressing use the documented execution endpoints."""
    aioclient_mock.post(url, text=JOB_UUID, headers=TEXT_HEADERS, status=201)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)
    path = "u/automation/lights" if kind is RunnableKind.SCRIPT else "f/home/night"

    job_id = await client.async_run_runnable(kind, path, {"room": "kitchen"}, **kwargs)

    assert job_id == JOB_UUID
    call = aioclient_mock.mock_calls[0]  # type: ignore[attr-defined]
    assert call[3]["Authorization"] == f"Bearer {TOKEN}"
    assert call[2] == {"room": "kitchen"}


@pytest.mark.parametrize("body", ["not-a-uuid", "", '"00000000-0000-4000-8000-00000000000z"'])
async def test_execution_rejects_invalid_job_identifiers(
    hass: HomeAssistant, aioclient_mock: object, body: str
) -> None:
    """An unusable job identifier fails closed instead of being registered."""
    aioclient_mock.post(RUN_SCRIPT_URL, text=body, headers=TEXT_HEADERS, status=201)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_run_runnable(RunnableKind.SCRIPT, "u/automation/lights", {})


@pytest.mark.parametrize(
    ("status", "exception_type"),
    [
        (HTTPStatus.UNAUTHORIZED, WindmillAuthenticationError),
        (HTTPStatus.FORBIDDEN, WindmillAuthorizationError),
        (HTTPStatus.NOT_FOUND, WindmillNotFoundError),
        (HTTPStatus.INTERNAL_SERVER_ERROR, WindmillServerError),
    ],
)
async def test_execution_status_mapping(
    hass: HomeAssistant,
    aioclient_mock: object,
    status: HTTPStatus,
    exception_type: type[Exception],
) -> None:
    """Execution keeps authentication, permission, missing and server failures distinct."""
    aioclient_mock.post(RUN_SCRIPT_URL, status=status)  # type: ignore[attr-defined]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(exception_type):
        await client.async_run_runnable(RunnableKind.SCRIPT, "u/automation/lights", {})


async def test_execution_rejects_unsafe_paths(hass: HomeAssistant) -> None:
    """An unsafe path never reaches the network layer."""
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(WindmillRequestError):
        await client.async_run_runnable(RunnableKind.SCRIPT, "u/../admin", {})


UPTODATE_URL = f"{BASE_URL}/api/uptodate"


@pytest.mark.parametrize(
    ("text", "installed", "latest", "up_to_date"),
    [
        ("yes", None, None, True),
        ("Update: 1.775.2 -> 1.780.0", "1.775.2", "1.780.0", False),
        ("Update: 1.775.2 -> 1.775.2", "1.775.2", "1.775.2", True),
        ("Update: dev -> 1.780.0-rc.1", "dev", "1.780.0-rc.1", False),
    ],
)
async def test_update_status_parsing(
    hass: HomeAssistant,
    aioclient_mock: object,
    text: str,
    installed: str | None,
    latest: str | None,
    up_to_date: bool,
) -> None:
    """Up-to-date, outdated and development builds are all parsed defensively."""
    aioclient_mock.get(UPTODATE_URL, text=text, headers=TEXT_HEADERS)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    status = await client.async_get_update_status()

    assert status.installed_version == installed
    assert status.latest_version == latest
    assert status.up_to_date is up_to_date
    assert "Authorization" not in aioclient_mock.mock_calls[0][3]  # type: ignore[attr-defined]


@pytest.mark.parametrize("text", ["no", "Update: 1.775.2", "", "x" * 300])
async def test_update_status_rejects_unparseable_text(
    hass: HomeAssistant, aioclient_mock: object, text: str
) -> None:
    """Unparseable update text fails closed instead of inventing a version."""
    aioclient_mock.get(UPTODATE_URL, text=text, headers=TEXT_HEADERS)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    with pytest.raises(WindmillProtocolError):
        await client.async_get_update_status()


async def test_update_status_maps_a_missing_endpoint(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """An old deployment without the endpoint is reported as not found."""
    aioclient_mock.get(UPTODATE_URL, status=HTTPStatus.NOT_FOUND)  # type: ignore[attr-defined]
    client = WindmillInstanceClient(async_get_clientsession(hass), BASE_URL, TOKEN)

    with pytest.raises(WindmillNotFoundError):
        await client.async_get_update_status()
