"""Tests for the independent asynchronous Windmill API client."""

import asyncio
import json
from http import HTTPStatus

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.windmill.api import (
    PageRequest,
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
    WindmillServerError,
    WindmillTimeoutError,
    WindmillUrlError,
    WindmillWorkspaceError,
    WindmillWorkspaceInfo,
    normalize_base_url,
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
