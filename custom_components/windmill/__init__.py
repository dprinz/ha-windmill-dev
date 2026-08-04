"""Windmill integration setup and config-entry lifecycle."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    is_managed_cloud,
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
    OPT_RUNNABLE_DETAILS,
    OPT_RUNNABLES,
    OPT_UPDATE_ENTITY,
    OPT_WORKER_DETAILS,
    OPT_WORKER_GROUPS,
)
from .coordinator import (
    ENTRY_STORES,
    RunnableSelection,
    RunObservationState,
    StartedJobRegistry,
    WindmillCapabilityCoordinator,
    WindmillHealthCoordinator,
    WindmillRunCoordinator,
    WindmillRunnableCoordinator,
    WindmillRunnableRunCoordinator,
    WindmillUpdateCoordinator,
    WindmillWorkerCoordinator,
    async_job_store,
    async_run_store,
    async_runnable_run_store,
    load_runnable_run_states,
    load_selections,
    run_scope_from_options,
)
from .entity import build_device_info
from .issues import async_delete_issues, async_evaluate_issues
from .models import WindmillRuntimeData
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)

type WindmillConfigEntry = ConfigEntry[WindmillRuntimeData]

# Instances are configured exclusively through the UI config flow; YAML is rejected.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.SENSOR,
    Platform.UPDATE,
]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register actions; YAML configuration of instances is intentionally ignored."""
    async_register_services(hass)
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

    started_jobs = StartedJobRegistry(async_job_store(hass, entry.entry_id))
    await started_jobs.async_load()

    selections = load_selections(entry.options.get(OPT_RUNNABLES))

    # Built before the run coordinator so the shared window can be handed to it from the very
    # first poll instead of only from the second one.
    runnable_run_coordinator: WindmillRunnableRunCoordinator | None = None
    if (
        selections
        and _feature_enabled(entry, OPT_RUNNABLE_DETAILS)
        and _supported(capabilities.runs)
    ):
        detail_store = async_runnable_run_store(hass, entry.entry_id)
        runnable_run_coordinator = WindmillRunnableRunCoordinator(
            hass,
            entry,
            client,
            detail_store,
            selections,
            load_runnable_run_states(await detail_store.async_load()),
        )
        await runnable_run_coordinator.async_config_entry_first_refresh()

    run_coordinator: WindmillRunCoordinator | None = None
    if _feature_enabled(entry, OPT_RUN_OBSERVATION) and _supported(capabilities.runs):
        store = async_run_store(hass, entry.entry_id)
        state = RunObservationState.from_dict(await store.async_load())
        scope = run_scope_from_options(entry.options)
        state.align_scope(scope)
        run_coordinator = WindmillRunCoordinator(
            hass,
            entry,
            client,
            store,
            state,
            scope=scope,
            selected=frozenset(selection.key for selection in selections),
            started_jobs=started_jobs,
            job_sink=(
                None
                if runnable_run_coordinator is None
                else runnable_run_coordinator.async_apply_window
            ),
        )
        await run_coordinator.async_config_entry_first_refresh()

    runnable_coordinator: WindmillRunnableCoordinator | None = None
    if selections and (
        _supported(capabilities.script_discovery) or _supported(capabilities.flow_discovery)
    ):
        runnable_coordinator = WindmillRunnableCoordinator(hass, entry, client, selections)
        await runnable_coordinator.async_config_entry_first_refresh()

    update_coordinator: WindmillUpdateCoordinator | None = None
    if (
        _feature_enabled(entry, OPT_UPDATE_ENTITY)
        and _supported(capabilities.update_visibility)
        and not is_managed_cloud(client.base_url)
    ):
        update_coordinator = WindmillUpdateCoordinator(hass, entry, client)
        # The upstream check depends on GitHub, so a failure must not fail setup.
        await update_coordinator.async_refresh()

    entry.runtime_data = WindmillRuntimeData(
        client=client,
        connection=connection,
        capability_coordinator=capability_coordinator,
        health_coordinator=health_coordinator,
        worker_coordinator=worker_coordinator,
        run_coordinator=run_coordinator,
        runnable_coordinator=runnable_coordinator,
        runnable_run_coordinator=runnable_run_coordinator,
        started_jobs=started_jobs,
        update_coordinator=update_coordinator,
    )
    # The workspace device is registered here rather than left to whichever entity happens to
    # reference it first: a per-runnable device points at it with `via_device`, and with every
    # workspace-level feature turned off no entity would create it at all.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **build_device_info(entry.entry_id, entry.title, entry.runtime_data),
    )
    # What survives is decided by configuration, never by a probe result: a runs capability
    # that answers 503 during one restart builds no coordinator, and treating that as "no
    # selections" would delete devices the user still has configured.
    _async_prune_runnable_devices(
        hass, entry, selections if _feature_enabled(entry, OPT_RUNNABLE_DETAILS) else ()
    )
    drift_since: dict[str, datetime] = {}

    @callback
    def _async_evaluate_issues() -> None:
        """Re-derive this entry's repair issues from the current observations."""
        async_evaluate_issues(hass, entry.entry_id, entry.options, entry.runtime_data, drift_since)

    _async_evaluate_issues()
    # Capabilities and worker versions are the two observations an issue depends on, so an issue
    # disappears on its own once the user fixed the permission or finished the upgrade.
    entry.async_on_unload(capability_coordinator.async_add_listener(_async_evaluate_issues))
    if worker_coordinator is not None:
        entry.async_on_unload(worker_coordinator.async_add_listener(_async_evaluate_issues))
    # An unloaded entry cannot substantiate a warning; setup re-derives every issue.
    entry.async_on_unload(lambda: async_delete_issues(hass, entry.entry_id))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WindmillConfigEntry) -> bool:
    """Unload platforms; config-entry callbacks stop the shared coordinators."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: WindmillConfigEntry) -> None:
    """Delete everything this config entry persisted.

    Home Assistant does not clean up `Store` files, so an unremoved entry would leave job
    identifiers, runnable paths and timestamps behind. Removal must never raise, or Home Assistant
    keeps the entry the user asked to delete.
    """
    for build_store in ENTRY_STORES:
        try:
            await build_store(hass, entry.entry_id).async_remove()
        except OSError:
            _LOGGER.warning(
                "Could not delete stored Windmill data of the removed config entry; "
                "the leftover file is only read by an entry with the same identifier"
            )


@callback
def _async_prune_runnable_devices(
    hass: HomeAssistant, entry: WindmillConfigEntry, selections: Sequence[RunnableSelection]
) -> None:
    """Remove the devices of runnables the user no longer exposes.

    A platform that stops adding an entity does not remove it: the registry keeps it as an
    orphan until Home Assistant is restarted, so a deselected runnable would leave a device
    full of permanently unavailable entities behind. Entity existence follows configuration
    here (ADR-0002), so the stale devices are dropped on the reload that changed it.
    """
    registry = dr.async_get(hass)
    expected = {(DOMAIN, entry.entry_id)} | {
        (DOMAIN, f"{entry.entry_id}_{selection.kind.value}_{selection.path}")
        for selection in selections
    }
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if device.identifiers & expected:
            continue
        registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


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
