"""Tests for Windmill config-entry setup, unload and reload."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.windmill import WindmillConfigEntry
from custom_components.windmill.api import (
    CapabilityAvailability,
    CapabilityMatrix,
    CapabilityReason,
    CapabilityStatus,
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillConnection,
    WindmillConnectionError,
    WindmillEdition,
    WindmillHealthState,
    WindmillHealthStatus,
    WindmillIdentity,
    WindmillProtocolError,
    WindmillRateLimitError,
    WindmillRequestError,
    WindmillServerError,
    WindmillServerInfo,
    WindmillUrlError,
    WindmillWorkspaceError,
)
from custom_components.windmill.const import (
    CONF_BASE_URL,
    CONF_TOKEN,
    CONF_WORKSPACE,
    DOMAIN,
)
from custom_components.windmill.coordinator import WindmillCapabilityCoordinator

ENTRY_DATA = {
    CONF_BASE_URL: "https://windmill.example",
    CONF_WORKSPACE: "home-assistant",
    CONF_TOKEN: "obviously-fake-test-token",
}
IDENTITY = WindmillIdentity(username="automation", is_admin=False, is_super_admin=False)
HEALTH = WindmillHealthStatus(
    status=WindmillHealthState.HEALTHY,
    checked_at=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
    database_healthy=True,
    workers_alive=2,
)
CONNECTION = WindmillConnection(
    identity=IDENTITY,
    server=WindmillServerInfo(edition=WindmillEdition.COMMUNITY, version="v1.775.2"),
)
AVAILABLE = CapabilityAvailability(
    status=CapabilityStatus.AVAILABLE,
    reason=CapabilityReason.PROBE_SUCCEEDED,
)
CONTEXT_REQUIRED = CapabilityAvailability(
    status=CapabilityStatus.NOT_APPLICABLE,
    reason=CapabilityReason.CONTEXT_REQUIRED,
)
CAPABILITIES = CapabilityMatrix(
    health=AVAILABLE,
    detailed_health=AVAILABLE,
    workers=AVAILABLE,
    runs=AVAILABLE,
    script_discovery=AVAILABLE,
    flow_discovery=AVAILABLE,
    script_execution=CONTEXT_REQUIRED,
    flow_execution=CONTEXT_REQUIRED,
    cancellation=CONTEXT_REQUIRED,
    update_visibility=AVAILABLE,
)


async def test_manifest_loads_through_home_assistant(hass: HomeAssistant) -> None:
    """Home Assistant recognizes the manifest and config-flow package structure."""
    integration = await loader.async_get_integration(hass, DOMAIN)

    assert integration.manifest["domain"] == DOMAIN
    assert integration.manifest["config_flow"] is True
    assert integration.manifest["integration_type"] == "service"
    assert integration.manifest["requirements"] == []


def _add_entry(hass: HomeAssistant) -> WindmillConfigEntry:
    """Add a typed fake Windmill config entry to Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, title="home-assistant", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    return entry


async def test_setup_unload_and_reload(hass: HomeAssistant) -> None:
    """The entry lifecycle works through Home Assistant's public interfaces."""
    entry = _add_entry(hass)
    connect = AsyncMock(return_value=CONNECTION)
    discover = AsyncMock(return_value=CAPABILITIES)
    shutdowns: list[WindmillCapabilityCoordinator] = []
    original_shutdown = WindmillCapabilityCoordinator.async_shutdown

    async def track_shutdown(coordinator: WindmillCapabilityCoordinator) -> None:
        shutdowns.append(coordinator)
        await original_shutdown(coordinator)

    with (
        patch("custom_components.windmill.api.WindmillClient.async_connect", new=connect),
        patch(
            "custom_components.windmill.api.WindmillClient.async_discover_capabilities",
            new=discover,
        ),
        patch(
            "custom_components.windmill.api.WindmillInstanceClient.async_get_health_status",
            new=AsyncMock(return_value=HEALTH),
        ),
        patch(
            "custom_components.windmill.coordinator.WindmillCapabilityCoordinator.async_shutdown",
            new=track_shutdown,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.identity == IDENTITY
        assert entry.runtime_data.server == CONNECTION.server
        assert entry.runtime_data.capabilities == CAPABILITIES

        hass.config_entries.async_update_entry(
            entry,
            data={**ENTRY_DATA, CONF_TOKEN: "rotated-obviously-fake-token"},
        )
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert not entry.update_listeners

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert connect.await_count == 2
        assert discover.await_count == 2

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED
        assert not hasattr(entry, "runtime_data")
        assert len(shutdowns) == 2


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (WindmillAuthenticationError(), ConfigEntryState.SETUP_ERROR),
        (WindmillConnectionError(), ConfigEntryState.SETUP_RETRY),
        (WindmillRateLimitError(), ConfigEntryState.SETUP_RETRY),
        (WindmillServerError(), ConfigEntryState.SETUP_RETRY),
        (WindmillAuthorizationError(), ConfigEntryState.SETUP_ERROR),
        (WindmillProtocolError(), ConfigEntryState.SETUP_ERROR),
        (WindmillRequestError(), ConfigEntryState.SETUP_ERROR),
        (WindmillUrlError(), ConfigEntryState.SETUP_ERROR),
        (WindmillWorkspaceError(), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_error_mapping(
    hass: HomeAssistant, error: Exception, expected_state: ConfigEntryState
) -> None:
    """Setup failures map to Home Assistant retry/auth/permanent states."""
    entry = _add_entry(hass)

    with patch(
        "custom_components.windmill.api.WindmillClient.async_connect",
        new=AsyncMock(side_effect=error),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is expected_state


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (WindmillAuthenticationError(), ConfigEntryState.SETUP_ERROR),
        (WindmillConnectionError(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_capability_coordinator_setup_error_mapping(
    hass: HomeAssistant,
    error: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Coordinator authentication and transport failures preserve HA semantics."""
    entry = _add_entry(hass)

    with (
        patch(
            "custom_components.windmill.api.WindmillClient.async_connect",
            new=AsyncMock(return_value=CONNECTION),
        ),
        patch(
            "custom_components.windmill.api.WindmillClient.async_discover_capabilities",
            new=AsyncMock(side_effect=error),
        ),
        patch(
            "custom_components.windmill.api.WindmillInstanceClient.async_get_health_status",
            new=AsyncMock(return_value=HEALTH),
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is expected_state
