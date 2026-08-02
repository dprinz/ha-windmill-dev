"""Windmill integration setup and config-entry lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import (
    CapabilityAvailability,
    CapabilityStatus,
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillClient,
    WindmillConnectionError,
    WindmillError,
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
    DOMAIN,
    FEATURE_DEFAULTS,
    OPT_DETAILED_HEALTH,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
    OPT_RUNNABLES,
    OPT_WORKER_DETAILS,
    OPT_WORKER_GROUPS,
)
from .coordinator import (
    RUN_STORAGE_VERSION,
    RunObservationState,
    WindmillCapabilityCoordinator,
    WindmillHealthCoordinator,
    WindmillRunCoordinator,
    WindmillRunnableCoordinator,
    WindmillWorkerCoordinator,
    load_selections,
)
from .models import WindmillRuntimeData

_LOGGER = logging.getLogger(__name__)

type WindmillConfigEntry = ConfigEntry[WindmillRuntimeData]

PLATFORMS = [Platform.BINARY_SENSOR, Platform.EVENT, Platform.SENSOR]


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

    worker_coordinator: WindmillWorkerCoordinator | None = None
    worker_features = _feature_enabled(entry, OPT_WORKER_GROUPS) or _feature_enabled(
        entry, OPT_WORKER_DETAILS
    )
    if worker_features and _supported(capabilities.workers):
        worker_coordinator = WindmillWorkerCoordinator(
            hass,
            entry,
            client,
            known_groups=await _async_configured_worker_groups(client),
        )
        await worker_coordinator.async_config_entry_first_refresh()

    run_coordinator: WindmillRunCoordinator | None = None
    if _feature_enabled(entry, OPT_RUN_OBSERVATION) and _supported(capabilities.runs):
        store: Store[dict[str, Any]] = Store(
            hass, RUN_STORAGE_VERSION, f"{DOMAIN}.runs.{entry.entry_id}"
        )
        run_coordinator = WindmillRunCoordinator(
            hass,
            entry,
            client,
            store,
            RunObservationState.from_dict(await store.async_load()),
        )
        await run_coordinator.async_config_entry_first_refresh()

    runnable_coordinator: WindmillRunnableCoordinator | None = None
    selections = load_selections(entry.options.get(OPT_RUNNABLES))
    if selections and (
        _supported(capabilities.script_discovery) or _supported(capabilities.flow_discovery)
    ):
        runnable_coordinator = WindmillRunnableCoordinator(hass, entry, client, selections)
        await runnable_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = WindmillRuntimeData(
        client=client,
        connection=connection,
        capability_coordinator=capability_coordinator,
        health_coordinator=health_coordinator,
        worker_coordinator=worker_coordinator,
        run_coordinator=run_coordinator,
        runnable_coordinator=runnable_coordinator,
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


async def _async_configured_worker_groups(client: WindmillClient) -> tuple[str, ...]:
    """Read configured worker groups, degrading to observed groups when denied."""
    try:
        return await client.async_list_worker_groups()
    except WindmillAuthenticationError as err:
        raise ConfigEntryAuthFailed("Windmill authentication failed") from err
    except WindmillError:
        _LOGGER.debug("Windmill worker groups are not listable; using observed groups instead")
        return ()
