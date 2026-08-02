"""Home Assistant System Health information for Windmill entries."""

from __future__ import annotations

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import CONF_BASE_URL, CONF_WORKSPACE, DOMAIN
from .models import WindmillRuntimeData


@callback
def async_register(hass: HomeAssistant, register: system_health.SystemHealthRegistration) -> None:
    """Register the Windmill system health callback."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Report credential-free connection identity, version and reachability."""
    info: dict[str, Any] = {}
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        runtime: WindmillRuntimeData = entry.runtime_data
        instance = f"{entry.data[CONF_BASE_URL]} ({entry.data[CONF_WORKSPACE]})"
        info[instance] = f"{runtime.server.edition.upper()} {runtime.server.version}"
        info[f"{instance} reachable"] = system_health.async_check_can_reach_url(
            hass, f"{runtime.client.base_url}/api/version"
        )
    return info
