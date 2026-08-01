"""Windmill integration setup and config-entry lifecycle."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillClient,
    WindmillConnectionError,
    WindmillProtocolError,
    WindmillRateLimitError,
    WindmillRequestError,
    WindmillServerError,
    WindmillUrlError,
    WindmillWorkspaceError,
)
from .const import CONF_BASE_URL, CONF_TOKEN, CONF_WORKSPACE
from .models import WindmillRuntimeData

type WindmillConfigEntry = ConfigEntry[WindmillRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the integration package; YAML configuration is intentionally ignored."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: WindmillConfigEntry) -> bool:
    """Validate and set up a Windmill config entry."""
    try:
        client = WindmillClient(
            async_get_clientsession(hass),
            entry.data[CONF_BASE_URL],
            entry.data[CONF_WORKSPACE],
            entry.data[CONF_TOKEN],
        )
        identity = await client.async_validate()
    except WindmillAuthenticationError as err:
        raise ConfigEntryAuthFailed("Windmill authentication failed") from err
    except (WindmillConnectionError, WindmillRateLimitError, WindmillServerError) as err:
        raise ConfigEntryNotReady("Windmill is temporarily unavailable") from err
    except (
        WindmillAuthorizationError,
        WindmillProtocolError,
        WindmillRequestError,
        WindmillUrlError,
        WindmillWorkspaceError,
    ) as err:
        raise ConfigEntryError("Windmill configuration is no longer valid") from err

    entry.runtime_data = WindmillRuntimeData(client=client, identity=identity)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WindmillConfigEntry) -> bool:
    """Unload a Windmill config entry with no platforms or private sessions to release."""
    return True


async def _async_update_listener(hass: HomeAssistant, entry: WindmillConfigEntry) -> None:
    """Reload the entry after supported config-entry updates."""
    await hass.config_entries.async_reload(entry.entry_id)
