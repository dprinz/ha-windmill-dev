"""Tests for read-only Windmill update visibility."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.windmill.api import (
    CapabilityAvailability,
    CapabilityReason,
    CapabilityStatus,
    WindmillConnectionError,
    WindmillNotFoundError,
    WindmillUpdateStatus,
    is_managed_cloud,
    release_url,
)
from custom_components.windmill.const import (
    CONF_BASE_URL,
    DOMAIN,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
    OPT_UPDATE_ENTITY,
)
from tests.test_health import CONNECTION, ENTRY_DATA, WORKSPACE, _capabilities

UNSUPPORTED = CapabilityAvailability(
    CapabilityStatus.UNSUPPORTED, CapabilityReason.ENDPOINT_MISSING
)
UPDATE_OPTIONS = {
    OPT_INSTANCE_HEALTH: False,
    OPT_RUN_OBSERVATION: False,
    OPT_UPDATE_ENTITY: True,
}
UP_TO_DATE = WindmillUpdateStatus(installed_version=None, latest_version=None, up_to_date=True)
OUTDATED = WindmillUpdateStatus(
    installed_version="1.775.2", latest_version="1.780.0", up_to_date=False
)
ENTITY_ID = "update.home_assistant_windmill_server"


def _as_mock(value: Any) -> AsyncMock:
    """Return an asynchronous mock returning or raising the supplied value."""
    if isinstance(value, Exception):
        return AsyncMock(side_effect=value)
    return AsyncMock(return_value=value)


@contextmanager
def patched_client(*, status: Any = OUTDATED, capabilities: Any = None) -> Iterator[dict[str, Any]]:
    """Patch every Windmill call an update-enabled config entry performs."""
    mocks = {
        "connect": _as_mock(CONNECTION),
        "capabilities": _as_mock(capabilities if capabilities is not None else _capabilities()),
        "update": _as_mock(status),
    }
    targets = {
        "connect": "custom_components.windmill.api.WindmillClient.async_connect",
        "capabilities": (
            "custom_components.windmill.api.WindmillClient.async_discover_capabilities"
        ),
        "update": "custom_components.windmill.api.WindmillInstanceClient.async_get_update_status",
    }
    with ExitStack() as stack:
        for key, target in targets.items():
            stack.enter_context(patch(target, new=mocks[key]))
        yield mocks


async def _setup_entry(
    hass: HomeAssistant,
    *,
    status: Any = OUTDATED,
    capabilities: Any = None,
    options: dict[str, Any] | None = None,
    base_url: str | None = None,
) -> MockConfigEntry:
    """Set up one loaded Windmill entry with update visibility enabled."""
    data = dict(ENTRY_DATA)
    if base_url is not None:
        data[CONF_BASE_URL] = base_url
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=WORKSPACE,
        data=data,
        options={**UPDATE_OPTIONS, **(options or {})},
    )
    entry.add_to_hass(hass)
    with patched_client(status=status, capabilities=capabilities):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_outdated_instance_reports_versions_and_release_url(hass: HomeAssistant) -> None:
    """An outdated deployment reports both versions and a safe release URL."""
    await _setup_entry(hass)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes["installed_version"] == "1.775.2"
    assert state.attributes["latest_version"] == "1.780.0"
    assert (
        state.attributes["release_url"]
        == "https://github.com/windmill-labs/windmill/releases/tag/v1.780.0"
    )
    assert state.attributes["auto_update"] is False
    assert state.attributes["supported_features"] == 0


async def test_up_to_date_instance_falls_back_to_the_connection_version(
    hass: HomeAssistant,
) -> None:
    """An up-to-date deployment reports the connected version for both fields."""
    await _setup_entry(hass, status=UP_TO_DATE)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes["installed_version"] == CONNECTION.server.version
    assert state.attributes["latest_version"] == CONNECTION.server.version


async def test_failed_update_check_never_fails_setup(hass: HomeAssistant) -> None:
    """A failing best-effort check leaves the entry loaded and the entity unavailable."""
    entry = await _setup_entry(hass, status=WindmillConnectionError())

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    with patched_client():
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=7))
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.parametrize(
    ("options", "capabilities", "base_url"),
    [
        ({OPT_UPDATE_ENTITY: False}, None, None),
        (None, _capabilities(update_visibility=UNSUPPORTED), None),
        (None, None, "https://app.windmill.dev"),
    ],
)
async def test_ineligible_deployments_expose_no_entity(
    hass: HomeAssistant,
    options: dict[str, Any] | None,
    capabilities: Any,
    base_url: str | None,
) -> None:
    """Opt-out, unsupported endpoints and managed Cloud never create the entity."""
    entry = await _setup_entry(hass, options=options, capabilities=capabilities, base_url=base_url)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID) is None


async def test_update_check_does_not_block_health_updates(hass: HomeAssistant) -> None:
    """The update check runs on its own slow schedule, separate from health polling."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data.update_coordinator

    assert coordinator.update_interval == timedelta(hours=6)
    assert entry.runtime_data.health_coordinator is None

    with patched_client() as mocks:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=30))
        await hass.async_block_till_done()

    assert mocks["update"].await_count == 0


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.775.2", "https://github.com/windmill-labs/windmill/releases/tag/v1.775.2"),
        ("v1.775.2", "https://github.com/windmill-labs/windmill/releases/tag/v1.775.2"),
        ("1.775.2-rc.1", "https://github.com/windmill-labs/windmill/releases/tag/v1.775.2-rc.1"),
        ("dev", None),
        ("1.775.2 && rm -rf /", None),
        ("../../evil", None),
        (None, None),
    ],
)
def test_release_urls_are_built_only_from_safe_versions(
    version: str | None, expected: str | None
) -> None:
    """Development builds and unsafe strings never become a release URL."""
    assert release_url(version) == expected


@pytest.mark.parametrize(
    ("base_url", "managed"),
    [
        ("https://app.windmill.dev", True),
        ("https://windmill.dev", True),
        ("https://windmill.example.com", False),
        ("https://windmill.dev.example.com", False),
        ("http://localhost:8000", False),
    ],
)
def test_managed_cloud_detection(base_url: str, managed: bool) -> None:
    """Managed Cloud hosts are recognized without touching the network."""
    assert is_managed_cloud(base_url) is managed


async def test_unsupported_update_endpoint_keeps_the_entry_loaded(hass: HomeAssistant) -> None:
    """An old deployment without the update endpoint stays usable."""
    entry = await _setup_entry(hass, status=WindmillNotFoundError())

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
