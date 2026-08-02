"""Tests for redacted Windmill config-entry diagnostics."""

import json

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.windmill.const import (
    CONF_TOKEN,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
    OPT_RUNNABLES,
)
from tests.test_health import BASE_URL, ENTRY_DATA, WORKSPACE
from tests.test_health import _setup_entry as _setup_health_entry
from tests.test_runnables import LIGHTS_SELECTION, _setup_entry


async def test_diagnostics_report_bounded_metadata(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Diagnostics describe the entry, instance, options, capabilities and coordinators."""
    assert await async_setup_component(hass, "diagnostics", {})
    entry = await _setup_entry(
        hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION], OPT_RUN_OBSERVATION: False}
    )

    report = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert report["instance"]["managed_cloud"] is False
    assert report["instance"]["edition"] == "ce"
    assert report["instance"]["version"] == "v1.775.2"
    assert report["options"]["selected_runnables"] == 1
    assert report["options"]["selection_modes"] == ["latest"]
    assert report["capabilities"]["health"] == {
        "status": "available",
        "reason": "probe_succeeded",
    }
    assert report["capabilities"]["script_execution"]["status"] == "not_applicable"
    assert report["coordinators"]["capabilities"]["last_update_success"] is True
    assert report["coordinators"]["runs"] == {"enabled": False}
    assert report["coordinators"]["runnables"]["update_interval_seconds"] == 1800.0
    assert report["started_jobs"] == {"tracked": 0}


async def test_diagnostics_redact_credentials_and_identity(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """No token, URL or workspace name survives a diagnostics download."""
    assert await async_setup_component(hass, "diagnostics", {})
    entry = await _setup_entry(hass)

    report = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    serialized = json.dumps(report)

    assert ENTRY_DATA[CONF_TOKEN] not in serialized
    assert BASE_URL not in serialized
    assert WORKSPACE not in serialized
    assert report["instance"]["base_url"] == REDACTED
    assert report["entry"]["title"] == REDACTED
    assert report["entry"]["data_keys"] == ["base_url", "token", "workspace"]
    for forbidden in ("arguments", "result", "logs", "traceback", "authorization"):
        assert forbidden not in serialized.lower()
    for forbidden in ("arguments", "result", "logs", "traceback", "authorization"):
        assert forbidden not in serialized.lower()


async def test_diagnostics_report_effective_feature_defaults(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """An entry whose options flow was never opened reports the effective defaults."""
    assert await async_setup_component(hass, "diagnostics", {})
    entry = await _setup_health_entry(hass, options={})

    report = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert report["options"]["instance_health"] is True
    assert report["options"]["run_observation"] is True
    assert report["options"]["detailed_health"] is False
    assert report["options"]["worker_groups"] is False
    assert report["options"]["worker_details"] is False
    assert report["options"]["update_entity"] is False
    assert report["options"]["runnable_buttons"] is False


async def test_diagnostics_report_explicitly_disabled_features(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """An explicit opt-out is reported as disabled, not masked by the defaults."""
    assert await async_setup_component(hass, "diagnostics", {})
    entry = await _setup_health_entry(
        hass, options={OPT_INSTANCE_HEALTH: False, OPT_RUN_OBSERVATION: False}
    )

    report = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert report["options"]["instance_health"] is False
    assert report["options"]["run_observation"] is False
