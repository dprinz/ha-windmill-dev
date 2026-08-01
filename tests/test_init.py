"""Tests for Windmill config-entry setup, unload and reload."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.windmill import WindmillConfigEntry
from custom_components.windmill.api import (
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillConnectionError,
    WindmillIdentity,
    WindmillProtocolError,
    WindmillRateLimitError,
    WindmillRequestError,
    WindmillServerError,
    WindmillUrlError,
    WindmillWorkspaceError,
)
from custom_components.windmill.const import (
    CONF_BASE_URL,
    CONF_TOKEN,
    CONF_WORKSPACE,
    DOMAIN,
)

ENTRY_DATA = {
    CONF_BASE_URL: "https://windmill.example",
    CONF_WORKSPACE: "home-assistant",
    CONF_TOKEN: "obviously-fake-test-token",
}
IDENTITY = WindmillIdentity(username="automation", is_admin=False, is_super_admin=False)


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
    validate = AsyncMock(return_value=IDENTITY)

    with patch("custom_components.windmill.api.WindmillClient.async_validate", new=validate):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.identity == IDENTITY

        hass.config_entries.async_update_entry(
            entry,
            data={**ENTRY_DATA, CONF_TOKEN: "rotated-obviously-fake-token"},
        )
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert validate.await_count == 2

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED


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
        "custom_components.windmill.api.WindmillClient.async_validate",
        new=AsyncMock(side_effect=error),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is expected_state
