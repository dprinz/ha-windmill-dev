"""Tests for the Windmill System Health registration."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, get_system_health_info
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.windmill.api import WindmillConnectionError
from custom_components.windmill.const import CONF_TOKEN, DOMAIN
from tests.test_health import BASE_URL, CONNECTION, ENTRY_DATA, WORKSPACE, patched_client


async def _resolved_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return System Health information with pending checks awaited."""
    info = await get_system_health_info(hass, DOMAIN)
    return {
        key: (await value if asyncio.iscoroutine(value) else value) for key, value in info.items()
    }


async def test_system_health_reports_identity_without_credentials(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """System Health reports instance identity, version and reachability only."""
    assert await async_setup_component(hass, "system_health", {})
    aioclient_mock.get(f"{BASE_URL}/api/version", text="CE v1.775.2")
    entry = MockConfigEntry(domain=DOMAIN, title=WORKSPACE, data=ENTRY_DATA, options={})
    entry.add_to_hass(hass)

    with patched_client():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        info = await _resolved_info(hass)

    instance = f"{BASE_URL} ({WORKSPACE})"
    assert info == {
        instance: f"CE {CONNECTION.server.version}",
        f"{instance} reachable": "ok",
    }
    assert ENTRY_DATA[CONF_TOKEN] not in str(info)


async def test_system_health_reports_unreachable_instance(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An unreachable instance is reported without failing System Health."""
    assert await async_setup_component(hass, "system_health", {})
    aioclient_mock.get(f"{BASE_URL}/api/version", exc=TimeoutError)
    entry = MockConfigEntry(domain=DOMAIN, title=WORKSPACE, data=ENTRY_DATA, options={})
    entry.add_to_hass(hass)

    with patched_client():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        info = await _resolved_info(hass)

    assert info[f"{BASE_URL} ({WORKSPACE}) reachable"] == {"type": "failed", "error": "timeout"}


async def test_system_health_skips_entries_that_are_not_loaded(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An entry that failed to load contributes no System Health rows."""
    assert await async_setup_component(hass, "system_health", {})
    entry = MockConfigEntry(domain=DOMAIN, title=WORKSPACE, data=ENTRY_DATA, options={})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.windmill.api.WindmillClient.async_connect",
        new=AsyncMock(side_effect=WindmillConnectionError()),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert await _resolved_info(hass) == {}
