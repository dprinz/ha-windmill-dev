"""Home Assistant coordinators for shared Windmill runtime data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CapabilityMatrix,
    WindmillAuthenticationError,
    WindmillClient,
    WindmillDetailedHealth,
    WindmillError,
    WindmillHealthStatus,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CAPABILITY_UPDATE_INTERVAL = timedelta(hours=6)
HEALTH_UPDATE_INTERVAL = timedelta(seconds=60)


@dataclass(frozen=True, slots=True)
class WindmillHealthSnapshot:
    """One immutable health observation shared by every health entity."""

    status: WindmillHealthStatus
    detailed: WindmillDetailedHealth | None


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
