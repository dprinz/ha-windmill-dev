"""Home Assistant coordinators for shared Windmill runtime data."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CapabilityMatrix,
    PageRequest,
    WindmillAuthenticationError,
    WindmillClient,
    WindmillDetailedHealth,
    WindmillError,
    WindmillHealthStatus,
    WindmillWorker,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CAPABILITY_UPDATE_INTERVAL = timedelta(hours=6)
HEALTH_UPDATE_INTERVAL = timedelta(seconds=60)
WORKER_UPDATE_INTERVAL = timedelta(minutes=2)
WORKER_PAGE_SIZE = 100
MAX_WORKER_PAGES = 5


@dataclass(frozen=True, slots=True)
class WindmillHealthSnapshot:
    """One immutable health observation shared by every health entity."""

    status: WindmillHealthStatus
    detailed: WindmillDetailedHealth | None


@dataclass(frozen=True, slots=True)
class WorkerGroupState:
    """Bounded aggregate of the alive workers of one worker group."""

    alive_workers: int = 0
    versions: int = 0


@dataclass(frozen=True, slots=True)
class WindmillWorkerSnapshot:
    """One immutable worker observation shared by every worker entity."""

    groups: Mapping[str, WorkerGroupState]
    instances: Mapping[str, int]


class WindmillCapabilityCoordinator(DataUpdateCoordinator[CapabilityMatrix]):
    """Share a bounded capability snapshot across later platforms."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        client: WindmillClient,
    ) -> None:
        """Initialize the config-entry-owned capability coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} capabilities",
            config_entry=entry,
            update_interval=CAPABILITY_UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> CapabilityMatrix:
        """Refresh the safe read-only capability matrix."""
        try:
            return await self.client.async_discover_capabilities()
        except WindmillAuthenticationError as err:
            raise ConfigEntryAuthFailed("Windmill authentication failed") from err
        except WindmillError as err:
            raise UpdateFailed("Unable to refresh Windmill capabilities") from err


class WindmillHealthCoordinator(DataUpdateCoordinator[WindmillHealthSnapshot]):
    """Poll instance health once for every health entity of a config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        client: WindmillClient,
        *,
        detailed: bool,
    ) -> None:
        """Initialize the config-entry-owned health coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} health",
            config_entry=entry,
            update_interval=HEALTH_UPDATE_INTERVAL,
        )
        self.client = client
        self.detailed = detailed

    async def _async_update_data(self) -> WindmillHealthSnapshot:
        """Refresh coarse health and, when enabled, the additive detailed health."""
        try:
            status = await self.client.async_get_health_status()
        except WindmillAuthenticationError as err:
            raise ConfigEntryAuthFailed("Windmill authentication failed") from err
        except WindmillError as err:
            raise UpdateFailed("Unable to refresh Windmill health") from err

        detailed: WindmillDetailedHealth | None = None
        if self.detailed:
            try:
                detailed = await self.client.async_get_detailed_health()
            except WindmillAuthenticationError as err:
                raise ConfigEntryAuthFailed("Windmill authentication failed") from err
            except WindmillError:
                # Detailed health is administrative and additive; coarse health still applies.
                _LOGGER.debug("Detailed Windmill health is currently unavailable")
        return WindmillHealthSnapshot(status=status, detailed=detailed)


class WindmillWorkerCoordinator(DataUpdateCoordinator[WindmillWorkerSnapshot]):
    """Poll a bounded worker listing once for every worker entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[Any],
        client: WindmillClient,
        *,
        known_groups: tuple[str, ...],
    ) -> None:
        """Initialize the config-entry-owned worker coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} workers",
            config_entry=entry,
            update_interval=WORKER_UPDATE_INTERVAL,
        )
        self.client = client
        self.known_groups = known_groups

    async def _async_update_data(self) -> WindmillWorkerSnapshot:
        """Walk a bounded number of worker pages and aggregate them safely."""
        workers: list[WindmillWorker] = []
        try:
            for page in range(1, MAX_WORKER_PAGES + 1):
                rows = await self.client.async_list_workers(
                    PageRequest(page=page, per_page=WORKER_PAGE_SIZE)
                )
                workers.extend(rows)
                if len(rows) < WORKER_PAGE_SIZE:
                    break
            else:
                _LOGGER.debug(
                    "Windmill reported more than %s alive workers; counts are a lower bound",
                    MAX_WORKER_PAGES * WORKER_PAGE_SIZE,
                )
        except WindmillAuthenticationError as err:
            raise ConfigEntryAuthFailed("Windmill authentication failed") from err
        except WindmillError as err:
            raise UpdateFailed("Unable to refresh Windmill workers") from err

        return self._aggregate(workers)

    def _aggregate(self, workers: list[WindmillWorker]) -> WindmillWorkerSnapshot:
        """Reduce worker rows to bounded per-group and per-instance counts."""
        counts: dict[str, int] = dict.fromkeys(self.known_groups, 0)
        versions: dict[str, set[str]] = {group: set() for group in self.known_groups}
        instances: dict[str, int] = {}
        for worker in workers:
            counts[worker.group] = counts.get(worker.group, 0) + 1
            versions.setdefault(worker.group, set()).add(worker.version)
            instances[worker.instance] = instances.get(worker.instance, 0) + 1
        groups = {
            group: WorkerGroupState(alive_workers=alive, versions=len(versions[group]))
            for group, alive in counts.items()
        }
        return WindmillWorkerSnapshot(groups=groups, instances=instances)
