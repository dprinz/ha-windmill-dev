"""Tests for the Windmill instance health entities."""

import logging
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.windmill.api import (
    CapabilityAvailability,
    CapabilityMatrix,
    CapabilityReason,
    CapabilityStatus,
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillConnection,
    WindmillConnectionError,
    WindmillDetailedHealth,
    WindmillEdition,
    WindmillHealthState,
    WindmillHealthStatus,
    WindmillIdentity,
    WindmillRateLimitError,
    WindmillServerInfo,
)
from custom_components.windmill.const import (
    CONF_BASE_URL,
    CONF_TOKEN,
    CONF_WORKSPACE,
    DOMAIN,
    MAX_RATE_LIMIT_BACKOFF_SECONDS,
    OPT_DETAILED_HEALTH,
    OPT_INSTANCE_HEALTH,
)
from custom_components.windmill.coordinator import HEALTH_UPDATE_INTERVAL

BASE_URL = "https://windmill.example"
WORKSPACE = "home-assistant"
ENTRY_DATA = {
    CONF_BASE_URL: BASE_URL,
    CONF_WORKSPACE: WORKSPACE,
    CONF_TOKEN: "obviously-fake-test-token",
}
SERVER = WindmillServerInfo(edition=WindmillEdition.COMMUNITY, version="v1.775.2")
CONNECTION = WindmillConnection(
    identity=WindmillIdentity(username="automation", is_admin=False, is_super_admin=False),
    server=SERVER,
)
AVAILABLE = CapabilityAvailability(CapabilityStatus.AVAILABLE, CapabilityReason.PROBE_SUCCEEDED)
UNAUTHORIZED = CapabilityAvailability(
    CapabilityStatus.UNAUTHORIZED, CapabilityReason.PERMISSION_DENIED
)
UNSUPPORTED = CapabilityAvailability(
    CapabilityStatus.UNSUPPORTED, CapabilityReason.ENDPOINT_MISSING
)
CONTEXT_REQUIRED = CapabilityAvailability(
    CapabilityStatus.NOT_APPLICABLE, CapabilityReason.CONTEXT_REQUIRED
)


def _capabilities(
    *,
    health: CapabilityAvailability = AVAILABLE,
    detailed: CapabilityAvailability = AVAILABLE,
    workers: CapabilityAvailability = AVAILABLE,
    runs: CapabilityAvailability = AVAILABLE,
    script_discovery: CapabilityAvailability = AVAILABLE,
    flow_discovery: CapabilityAvailability = AVAILABLE,
    update_visibility: CapabilityAvailability = AVAILABLE,
) -> CapabilityMatrix:
    """Build a capability matrix with the capabilities under test."""
    return CapabilityMatrix(
        health=health,
        detailed_health=detailed,
        workers=workers,
        runs=runs,
        script_discovery=script_discovery,
        flow_discovery=flow_discovery,
        script_execution=CONTEXT_REQUIRED,
        flow_execution=CONTEXT_REQUIRED,
        cancellation=CONTEXT_REQUIRED,
        update_visibility=update_visibility,
    )


HEALTH = WindmillHealthStatus(
    status=WindmillHealthState.HEALTHY,
    checked_at=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
    database_healthy=True,
    workers_alive=2,
)
DETAILED = WindmillDetailedHealth(
    status=WindmillHealthState.DEGRADED,
    checked_at=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
    database_healthy=True,
    workers_alive=2,
    pending_jobs=3,
    running_jobs=1,
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
    health: Any = HEALTH,
    detailed: Any = DETAILED,
    jobs: Any = (),
) -> Iterator[dict[str, AsyncMock]]:
    """Patch every Windmill call the config entry performs."""
    mocks = {
        "connect": _as_mock(CONNECTION),
        "capabilities": _as_mock(capabilities if capabilities is not None else _capabilities()),
        "health": _as_mock(health),
        "detailed": _as_mock(detailed),
        "jobs": _as_mock(jobs),
    }
    targets = {
        "connect": "custom_components.windmill.api.WindmillClient.async_connect",
        "capabilities": (
            "custom_components.windmill.api.WindmillClient.async_discover_capabilities"
        ),
        "health": "custom_components.windmill.api.WindmillInstanceClient.async_get_health_status",
        "detailed": (
            "custom_components.windmill.api.WindmillInstanceClient.async_get_detailed_health"
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
    options: dict[str, bool] | None = None,
    capabilities: CapabilityMatrix | None = None,
    health: Any = HEALTH,
    detailed: Any = DETAILED,
) -> MockConfigEntry:
    """Set up one loaded Windmill entry with the supplied feature options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=WORKSPACE,
        data=ENTRY_DATA,
        options=options if options is not None else {OPT_DETAILED_HEALTH: True},
    )
    entry.add_to_hass(hass)
    with patched_client(capabilities=capabilities, health=health, detailed=detailed):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_health_entities_expose_bounded_state(hass: HomeAssistant) -> None:
    """Enabled health monitoring exposes the documented bounded entity set."""
    entry = await _setup_entry(hass)

    assert entry.state is ConfigEntryState.LOADED
    health = hass.states.get("sensor.home_assistant_health")
    assert health is not None
    assert health.state == "healthy"
    assert health.attributes["device_class"] == "enum"
    assert health.attributes["options"] == ["healthy", "degraded", "unhealthy"]
    assert hass.states.get("sensor.home_assistant_alive_workers").state == "2"
    assert hass.states.get("sensor.home_assistant_pending_jobs").state == "3"
    assert hass.states.get("sensor.home_assistant_running_jobs").state == "1"
    assert hass.states.get("binary_sensor.home_assistant_database").state == "on"
    assert ENTRY_DATA[CONF_TOKEN] not in str(health.attributes)


async def test_health_entities_use_one_service_device(hass: HomeAssistant) -> None:
    """Every health entity belongs to the single credential-free instance device."""
    entry = await _setup_entry(hass)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.configuration_url == BASE_URL
    assert device.sw_version == SERVER.version
    assert device.manufacturer == "Windmill"

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 10
    assert {registered.device_id for registered in entities} == {device.id}
    assert all(registered.unique_id.startswith(entry.entry_id) for registered in entities)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (WindmillHealthState.HEALTHY, "healthy"),
        (WindmillHealthState.DEGRADED, "degraded"),
        (WindmillHealthState.UNHEALTHY, "unhealthy"),
    ],
)
async def test_overall_status_mapping(
    hass: HomeAssistant, state: WindmillHealthState, expected: str
) -> None:
    """Every upstream health state maps to one documented entity state."""
    await _setup_entry(
        hass,
        health=WindmillHealthStatus(
            status=state,
            checked_at=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
            database_healthy=False,
            workers_alive=0,
        ),
    )

    assert hass.states.get("sensor.home_assistant_health").state == expected
    assert hass.states.get("binary_sensor.home_assistant_database").state == "off"


async def test_health_failure_marks_entities_unavailable_and_recovers(
    hass: HomeAssistant,
) -> None:
    """A temporary health failure degrades to unavailable and recovers afterwards."""
    await _setup_entry(hass)

    with patched_client(health=WindmillConnectionError()):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done()

    assert hass.states.get("sensor.home_assistant_health").state == STATE_UNAVAILABLE

    with patched_client():
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=4))
        await hass.async_block_till_done()

    assert hass.states.get("sensor.home_assistant_health").state == "healthy"


async def test_denied_detailed_health_keeps_coarse_entities(hass: HomeAssistant) -> None:
    """A denied administrative call never takes down the core health entities."""
    await _setup_entry(hass, detailed=WindmillAuthorizationError())

    assert hass.states.get("sensor.home_assistant_health").state == "healthy"
    assert hass.states.get("sensor.home_assistant_pending_jobs").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.home_assistant_running_jobs").state == STATE_UNAVAILABLE


async def test_unauthorized_detailed_capability_creates_no_queue_entities(
    hass: HomeAssistant,
) -> None:
    """Queue diagnostics require both the opt-in and a supporting capability."""
    await _setup_entry(hass, capabilities=_capabilities(detailed=UNAUTHORIZED))

    assert hass.states.get("sensor.home_assistant_health") is not None
    assert hass.states.get("sensor.home_assistant_pending_jobs") is None
    assert hass.states.get("sensor.home_assistant_running_jobs") is None


async def test_detailed_health_opt_out_creates_no_queue_entities(hass: HomeAssistant) -> None:
    """Detailed health stays disabled unless the user opts in."""
    await _setup_entry(hass, options={})

    assert hass.states.get("sensor.home_assistant_health") is not None
    assert hass.states.get("sensor.home_assistant_pending_jobs") is None


@pytest.mark.parametrize(
    ("options", "capabilities"),
    [
        ({OPT_INSTANCE_HEALTH: False}, None),
        (None, _capabilities(health=UNSUPPORTED)),
    ],
)
async def test_disabled_or_unsupported_health_creates_no_entities(
    hass: HomeAssistant, options: dict[str, bool] | None, capabilities: CapabilityMatrix | None
) -> None:
    """An opted-out or unsupported health feature loads the entry without entities."""
    entry = await _setup_entry(hass, options=options, capabilities=capabilities)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.home_assistant_health") is None
    assert hass.states.get("binary_sensor.home_assistant_database") is None


async def test_health_authentication_failure_triggers_reauth(hass: HomeAssistant) -> None:
    """A revoked token during health polling starts the reauthentication flow."""
    entry = await _setup_entry(hass)

    with patched_client(health=WindmillAuthenticationError()):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done()

    flows = [
        flow for flow in hass.config_entries.flow.async_progress() if flow["handler"] == DOMAIN
    ]
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]
    assert flows[0]["context"]["entry_id"] == entry.entry_id


async def test_detailed_authentication_failure_triggers_reauth(hass: HomeAssistant) -> None:
    """An administrative 401 is an authentication failure, not a capability outcome."""
    await _setup_entry(hass)

    with patched_client(detailed=WindmillAuthenticationError()):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done()

    flows = [
        flow for flow in hass.config_entries.flow.async_progress() if flow["handler"] == DOMAIN
    ]
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_health_polling_is_shared_by_all_entities(hass: HomeAssistant) -> None:
    """One refresh serves every entity instead of one request per entity."""
    await _setup_entry(hass)

    with patched_client() as mocks:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done()

    assert mocks["health"].await_count == 1
    assert mocks["detailed"].await_count == 1


async def test_rate_limiting_slows_polling_until_one_refresh_succeeds(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Windmill asking for a retry delay stops the integration from polling through it."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data.health_coordinator

    with patched_client(health=WindmillRateLimitError(retry_after=600.0)):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done()

    assert coordinator.update_interval == timedelta(seconds=600)

    with patched_client() as mocks:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done()

        assert mocks["health"].await_count == 0

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=700))
        await hass.async_block_till_done()

        assert mocks["health"].await_count == 1

    assert coordinator.update_interval == HEALTH_UPDATE_INTERVAL
    assert hass.states.get("sensor.home_assistant_health").state == "healthy"


async def test_rate_limit_backoff_is_bounded(hass: HomeAssistant) -> None:
    """A hostile or missing retry delay cannot take the integration offline indefinitely."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data.health_coordinator

    with patched_client(health=WindmillRateLimitError(retry_after=86_400.0)):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done()

    assert coordinator.update_interval == timedelta(seconds=MAX_RATE_LIMIT_BACKOFF_SECONDS)


async def test_repeated_failures_are_logged_once(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Repeated identical failures must not fill the log; only the first is an error."""
    await _setup_entry(hass)
    caplog.clear()

    for minutes in (2, 4, 6):
        with caplog.at_level(logging.DEBUG), patched_client(health=WindmillConnectionError()):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=minutes))
            await hass.async_block_till_done()

    errors = [
        record
        for record in caplog.records
        if record.levelno >= logging.ERROR and "windmill health" in record.getMessage().lower()
    ]
    assert len(errors) == 1
