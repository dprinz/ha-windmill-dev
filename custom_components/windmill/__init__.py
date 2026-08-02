"""Windmill integration setup and config-entry lifecycle."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    CapabilityAvailability,
    CapabilityStatus,
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
from .const import (
    CONF_BASE_URL,
    CONF_TOKEN,
    CONF_WORKSPACE,
    FEATURE_DEFAULTS,
    OPT_DETAILED_HEALTH,
    OPT_INSTANCE_HEALTH,
)
from .coordinator import WindmillCapabilityCoordinator, WindmillHealthCoordinator
from .models import WindmillRuntimeData

type WindmillConfigEntry = ConfigEntry[WindmillRuntimeData]

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


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
        connection = await client.async_connect()
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

    capability_coordinator = WindmillCapabilityCoordinator(hass, entry, client)
    await capability_coordinator.async_config_entry_first_refresh()
    capabilities = capability_coordinator.data

    health_coordinator: WindmillHealthCoordinator | None = None
    if _feature_enabled(entry, OPT_INSTANCE_HEALTH) and _supported(capabilities.health):
        health_coordinator = WindmillHealthCoordinator(
            hass,
            entry,
            client,
            detailed=(
                _feature_enabled(entry, OPT_DETAILED_HEALTH)
                and _supported(capabilities.detailed_health)
            ),
        )
        await health_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = WindmillRuntimeData(
        client=client,
        connection=connection,
        capability_coordinator=capability_coordinator,
        health_coordinator=health_coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WindmillConfigEntry) -> bool:
    """Unload platforms; config-entry callbacks stop the shared coordinators."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _feature_enabled(entry: WindmillConfigEntry, option: str) -> bool:
    """Return whether an opt-in feature is enabled for this config entry."""
    return bool(entry.options.get(option, FEATURE_DEFAULTS[option]))


def _supported(availability: CapabilityAvailability) -> bool:
    """Return whether a capability probe currently proves support."""
    return availability.status is CapabilityStatus.AVAILABLE
