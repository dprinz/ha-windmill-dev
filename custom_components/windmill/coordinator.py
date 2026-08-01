"""Home Assistant coordinators for shared Windmill runtime data."""

from __future__ import annotations

import logging
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
    WindmillError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CAPABILITY_UPDATE_INTERVAL = timedelta(hours=6)


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
