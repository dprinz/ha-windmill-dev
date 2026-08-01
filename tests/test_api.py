"""Tests for the independent asynchronous Windmill API client."""

from http import HTTPStatus

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.windmill.api import (
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillClient,
    WindmillConnectionError,
    WindmillProtocolError,
    WindmillRateLimitError,
    WindmillRequestError,
    WindmillServerError,
    WindmillTimeoutError,
    WindmillUrlError,
    WindmillWorkspaceError,
    normalize_base_url,
    normalize_workspace,
)

BASE_URL = "https://windmill.example"
WORKSPACE = "home-assistant"
VERSION_URL = f"{BASE_URL}/api/version"
WHOAMI_URL = f"{BASE_URL}/api/w/{WORKSPACE}/users/whoami"
TOKEN = "obviously-fake-test-token"
JSON_HEADERS = {"Content-Type": "application/json"}
TEXT_HEADERS = {"Content-Type": "text/plain"}


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

    identity = await client.async_validate()

    assert identity.username == "automation"
    assert identity.is_admin is False
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


@pytest.mark.parametrize(
    ("body", "content_length"),
    [
        ("{}", "invalid"),
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
