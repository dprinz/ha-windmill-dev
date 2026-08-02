"""Tests for safe read-only Windmill capability negotiation."""

import asyncio
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.windmill.api import (
    CapabilityAvailability,
    CapabilityReason,
    CapabilityStatus,
    WindmillAuthenticationError,
    WindmillClient,
)

BASE_URL = "https://windmill.example"
WORKSPACE = "home-assistant"
TOKEN = "obviously-fake-test-token"
HEALTH_URL = f"{BASE_URL}/api/health/status?force=false"
DETAILED_URL = f"{BASE_URL}/api/health/detailed"
WORKERS_URL = f"{BASE_URL}/api/workers/list?page=1&per_page=1&ping_since=300"
RUNS_URL = (
    f"{BASE_URL}/api/w/{WORKSPACE}/jobs/list"
    "?page=1&per_page=1&has_null_parent=true&is_flow_step=false"
)
SCRIPTS_URL = f"{BASE_URL}/api/w/{WORKSPACE}/scripts/list?page=1&per_page=1"
FLOWS_URL = f"{BASE_URL}/api/w/{WORKSPACE}/flows/list?page=1&per_page=1"
UPDATE_URL = f"{BASE_URL}/api/uptodate"
JSON_HEADERS = {"Content-Type": "application/json"}
TEXT_HEADERS = {"Content-Type": "text/plain"}
HEALTH_BODY = {
    "status": "healthy",
    "checked_at": "2026-08-02T10:00:00Z",
    "database_healthy": True,
    "workers_alive": 2,
}
DETAILED_BODY = {
    "status": "healthy",
    "checked_at": "2026-08-02T10:00:00Z",
    "version": "CE 1.775.2",
    "checks": {
        "database": {"healthy": True, "latency_ms": 3, "pool": {"size": 4, "idle": 2}},
        "workers": {"healthy": True, "active_count": 2, "versions": ["1.775.2"]},
        "queue": {"pending_jobs": 1, "running_jobs": 1},
        "readiness": {"healthy": True},
    },
}
SENTINEL_SECRET = "must-not-be-retained-secret"


def _mock_capabilities(
    aioclient_mock: object,
    *,
    health_status: int = HTTPStatus.OK,
    detailed_status: int = HTTPStatus.OK,
    workers_status: int = HTTPStatus.OK,
    runs_status: int = HTTPStatus.OK,
    scripts_status: int = HTTPStatus.OK,
    flows_status: int = HTTPStatus.OK,
    update_status: int = HTTPStatus.OK,
    workers_error: Exception | None = None,
    detailed_body: object | None = None,
    flows_body: object | None = None,
    update_text: str = "yes",
) -> None:
    """Register one bounded response for every fixed capability probe."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        HEALTH_URL,
        status=health_status,
        json=HEALTH_BODY if health_status in {200, 503} else None,
        headers=JSON_HEADERS,
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        DETAILED_URL,
        status=detailed_status,
        json=(detailed_body if detailed_body is not None else DETAILED_BODY)
        if detailed_status in {200, 503}
        else None,
        headers=JSON_HEADERS,
    )
    if workers_error is None:
        aioclient_mock.get(  # type: ignore[attr-defined]
            WORKERS_URL,
            status=workers_status,
            json=[{"token": SENTINEL_SECRET}] if workers_status == 200 else None,
            headers=JSON_HEADERS,
        )
    else:
        aioclient_mock.get(WORKERS_URL, exc=workers_error)  # type: ignore[attr-defined]
    aioclient_mock.get(  # type: ignore[attr-defined]
        RUNS_URL,
        status=runs_status,
        json=[] if runs_status == 200 else None,
        headers=JSON_HEADERS,
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        SCRIPTS_URL,
        status=scripts_status,
        json=[] if scripts_status == 200 else None,
        headers=JSON_HEADERS,
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        FLOWS_URL,
        status=flows_status,
        json=([] if flows_body is None else flows_body) if flows_status == 200 else None,
        headers=JSON_HEADERS,
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        UPDATE_URL,
        status=update_status,
        text=update_text if update_status == 200 else None,
        headers=TEXT_HEADERS,
    )


async def test_capability_matrix_uses_safe_bounded_probes(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """Successful reads expose capabilities without claiming write authorization."""
    _mock_capabilities(aioclient_mock)
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    matrix = await client.async_discover_capabilities()

    assert matrix.health.status is CapabilityStatus.AVAILABLE
    assert matrix.detailed_health.status is CapabilityStatus.AVAILABLE
    assert matrix.workers.status is CapabilityStatus.AVAILABLE
    assert matrix.runs.status is CapabilityStatus.AVAILABLE
    assert matrix.script_discovery.status is CapabilityStatus.AVAILABLE
    assert matrix.flow_discovery.status is CapabilityStatus.AVAILABLE
    assert matrix.script_execution.status is CapabilityStatus.NOT_APPLICABLE
    assert matrix.script_execution.reason is CapabilityReason.CONTEXT_REQUIRED
    assert matrix.flow_execution.status is CapabilityStatus.NOT_APPLICABLE
    assert matrix.cancellation.status is CapabilityStatus.NOT_APPLICABLE
    assert matrix.update_visibility.status is CapabilityStatus.AVAILABLE
    assert SENTINEL_SECRET not in repr(matrix)

    calls = aioclient_mock.mock_calls  # type: ignore[attr-defined]
    assert len(calls) == 7
    for call in calls:
        url = str(call[1])
        if url.startswith(f"{BASE_URL}/api/health/status") or url == UPDATE_URL:
            assert "Authorization" not in call[3]
        else:
            assert call[3]["Authorization"] == f"Bearer {TOKEN}"
        assert "per_page=1" in url or url in {HEALTH_URL, DETAILED_URL, UPDATE_URL}


@pytest.mark.parametrize(
    ("overrides", "field", "status", "reason"),
    [
        (
            {"health_status": HTTPStatus.UNAUTHORIZED},
            "health",
            CapabilityStatus.UNAUTHORIZED,
            CapabilityReason.PERMISSION_DENIED,
        ),
        (
            {"detailed_status": HTTPStatus.FORBIDDEN},
            "detailed_health",
            CapabilityStatus.UNAUTHORIZED,
            CapabilityReason.PERMISSION_DENIED,
        ),
        (
            {"detailed_body": []},
            "detailed_health",
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.UNEXPECTED_RESPONSE,
        ),
        (
            {"detailed_body": {**DETAILED_BODY, "status": "mystery"}},
            "detailed_health",
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.UNEXPECTED_RESPONSE,
        ),
        (
            {"detailed_body": {**DETAILED_BODY, "checked_at": ""}},
            "detailed_health",
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.UNEXPECTED_RESPONSE,
        ),
        (
            {"detailed_body": {**DETAILED_BODY, "checked_at": "not-a-time"}},
            "detailed_health",
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.UNEXPECTED_RESPONSE,
        ),
        (
            {"detailed_body": {**DETAILED_BODY, "version": ""}},
            "detailed_health",
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.UNEXPECTED_RESPONSE,
        ),
        (
            {"detailed_body": {**DETAILED_BODY, "checks": []}},
            "detailed_health",
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.UNEXPECTED_RESPONSE,
        ),
        (
            {"workers_status": HTTPStatus.NOT_FOUND},
            "workers",
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.ENDPOINT_MISSING,
        ),
        (
            {"runs_status": HTTPStatus.SERVICE_UNAVAILABLE},
            "runs",
            CapabilityStatus.TEMPORARILY_UNAVAILABLE,
            CapabilityReason.TEMPORARY_FAILURE,
        ),
        (
            {"scripts_status": HTTPStatus.FORBIDDEN},
            "script_discovery",
            CapabilityStatus.UNAUTHORIZED,
            CapabilityReason.PERMISSION_DENIED,
        ),
        (
            {"flows_body": [{}, {}]},
            "flow_discovery",
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.UNEXPECTED_RESPONSE,
        ),
        (
            {"update_text": "not-a-windmill-update-status"},
            "update_visibility",
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.UNEXPECTED_RESPONSE,
        ),
        (
            {"update_status": HTTPStatus.NOT_FOUND},
            "update_visibility",
            CapabilityStatus.UNSUPPORTED,
            CapabilityReason.ENDPOINT_MISSING,
        ),
    ],
)
async def test_optional_failures_are_capability_local(
    hass: HomeAssistant,
    aioclient_mock: object,
    overrides: dict[str, object],
    field: str,
    status: CapabilityStatus,
    reason: CapabilityReason,
) -> None:
    """Permission, support and temporary failures do not fail discovery."""
    _mock_capabilities(aioclient_mock, **overrides)  # type: ignore[arg-type]
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    matrix = await client.async_discover_capabilities()

    availability = getattr(matrix, field)
    assert availability.status is status
    assert availability.reason is reason
    assert matrix.script_execution.status is CapabilityStatus.NOT_APPLICABLE
    assert matrix.flow_execution.status is CapabilityStatus.NOT_APPLICABLE
    assert matrix.cancellation.status is CapabilityStatus.NOT_APPLICABLE


async def test_authenticated_probe_401_invalidates_authentication(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """An authenticated 401 remains distinct from optional permission denial."""
    _mock_capabilities(aioclient_mock, workers_status=HTTPStatus.UNAUTHORIZED)
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    with pytest.raises(WindmillAuthenticationError):
        await client.async_discover_capabilities()


async def test_probe_transport_failure_is_temporary(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """One optional transport failure does not discard other capability results."""
    _mock_capabilities(aioclient_mock, workers_error=aiohttp.ClientConnectionError())
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)

    matrix = await client.async_discover_capabilities()

    assert matrix.workers.status is CapabilityStatus.TEMPORARILY_UNAVAILABLE
    assert matrix.health.status is CapabilityStatus.AVAILABLE


async def test_authentication_failure_cancels_and_awaits_sibling_probes(
    hass: HomeAssistant,
) -> None:
    """An early authenticated 401 leaves no unowned capability task running."""
    client = WindmillClient(async_get_clientsession(hass), BASE_URL, WORKSPACE, TOKEN)
    slow_started = asyncio.Event()
    slow_cancelled = asyncio.Event()

    async def slow_health() -> None:
        slow_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            slow_cancelled.set()
            raise

    async def fail_auth(*args: object, **kwargs: object) -> CapabilityAvailability:
        await slow_started.wait()
        raise WindmillAuthenticationError

    available = CapabilityAvailability(
        CapabilityStatus.AVAILABLE,
        CapabilityReason.PROBE_SUCCEEDED,
    )
    with (
        patch.object(client, "async_get_health_status", new=slow_health),
        patch.object(client, "_probe_json_object", new=fail_auth),
        patch.object(client, "_probe_json_list", new=AsyncMock(return_value=available)),
        patch.object(client, "_probe_update_visibility", new=AsyncMock(return_value=available)),
        pytest.raises(WindmillAuthenticationError),
    ):
        await client.async_discover_capabilities()

    assert slow_cancelled.is_set()
