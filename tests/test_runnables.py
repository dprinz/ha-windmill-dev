"""Tests for explicit Windmill runnable discovery and selection."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.windmill.api import (
    AddressingMode,
    CapabilityAvailability,
    CapabilityReason,
    CapabilityStatus,
    RunnableDetails,
    RunnableKind,
    RunnableParameter,
    WindmillAuthorizationError,
    WindmillConnectionError,
    WindmillNotFoundError,
    WindmillRunnable,
)
from custom_components.windmill.const import (
    DOMAIN,
    MAX_SELECTED_RUNNABLES,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
    OPT_RUNNABLES,
)
from custom_components.windmill.coordinator import RunnableSelection, load_selections
from tests.test_health import CONNECTION, ENTRY_DATA, WORKSPACE, _capabilities

UNAUTHORIZED = CapabilityAvailability(
    CapabilityStatus.UNAUTHORIZED, CapabilityReason.PERMISSION_DENIED
)
LIGHTS = WindmillRunnable(
    kind=RunnableKind.SCRIPT, path="u/automation/lights", summary="Toggle the lights"
)
NIGHT = WindmillRunnable(kind=RunnableKind.FLOW, path="f/home/night", summary="")
BASE_OPTIONS = {OPT_INSTANCE_HEALTH: False, OPT_RUN_OBSERVATION: False}
LIGHTS_SELECTION = {
    "kind": "script",
    "path": "u/automation/lights",
    "mode": AddressingMode.LATEST.value,
}
LIGHTS_DETAILS = RunnableDetails(
    kind=RunnableKind.SCRIPT,
    path="u/automation/lights",
    summary="Toggle the lights",
    script_hash="0123456789abcdef",
    flow_version=None,
    parameters=(RunnableParameter(name="room", type="string", required=True),),
    schema_supported=True,
)
UNSUPPORTED_DETAILS = RunnableDetails(
    kind=RunnableKind.SCRIPT,
    path="u/automation/lights",
    summary="Toggle the lights",
    script_hash="0123456789abcdef",
    flow_version=None,
    parameters=(),
    schema_supported=False,
    schema_reason="unsupported_parameter_type",
)


def _as_mock(value: Any) -> AsyncMock:
    """Return an asynchronous mock returning or raising the supplied value."""
    if isinstance(value, Exception):
        return AsyncMock(side_effect=value)
    return AsyncMock(return_value=value)


@contextmanager
def patched_client(
    *,
    capabilities: Any = None,
    runnables: Any = (LIGHTS, NIGHT),
    details: Any = LIGHTS_DETAILS,
) -> Iterator[dict[str, AsyncMock]]:
    """Patch every Windmill call a selection-enabled config entry performs."""

    async def list_runnables(kind: RunnableKind, page: Any) -> tuple[WindmillRunnable, ...]:
        if isinstance(runnables, Exception):
            raise runnables
        return tuple(row for row in runnables if row.kind is kind)

    mocks = {
        "connect": _as_mock(CONNECTION),
        "capabilities": _as_mock(capabilities if capabilities is not None else _capabilities()),
        "runnables": AsyncMock(side_effect=list_runnables),
        "details": _as_mock(details),
    }
    targets = {
        "connect": "custom_components.windmill.api.WindmillClient.async_connect",
        "capabilities": (
            "custom_components.windmill.api.WindmillClient.async_discover_capabilities"
        ),
        "runnables": "custom_components.windmill.api.WindmillClient.async_list_runnables",
        "details": "custom_components.windmill.api.WindmillClient.async_get_runnable",
    }
    with ExitStack() as stack:
        for key, target in targets.items():
            stack.enter_context(patch(target, new=mocks[key]))
        yield mocks


async def _setup_entry(
    hass: HomeAssistant,
    *,
    options: dict[str, Any] | None = None,
    capabilities: Any = None,
    details: Any = LIGHTS_DETAILS,
    runnables: Any = (LIGHTS, NIGHT),
) -> MockConfigEntry:
    """Set up one loaded Windmill entry with the supplied runnable selection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=WORKSPACE,
        data=ENTRY_DATA,
        options={**BASE_OPTIONS, **(options or {})},
    )
    entry.add_to_hass(hass)
    with patched_client(capabilities=capabilities, details=details, runnables=runnables):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def _open_selection(hass: HomeAssistant, entry: MockConfigEntry) -> Any:
    """Open the runnable selection step of the options flow."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "runnables"}
    )


async def test_nothing_is_selected_by_default(hass: HomeAssistant) -> None:
    """A fresh entry exposes no runnable and starts no runnable coordinator."""
    entry = await _setup_entry(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.options.get(OPT_RUNNABLES) is None
    assert entry.runtime_data.runnable_coordinator is None


async def test_selection_form_lists_discovered_runnables(hass: HomeAssistant) -> None:
    """The selection form offers discovered scripts and flows with safe labels."""
    entry = await _setup_entry(hass)

    with patched_client():
        result = await _open_selection(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "runnables"
    selector = next(iter(result["data_schema"].schema.values()))
    values = [option["value"] for option in selector.config["options"]]
    labels = [option["label"] for option in selector.config["options"]]
    assert values == ["flow:f/home/night", "script:u/automation/lights"]
    assert "script: u/automation/lights - Toggle the lights" in labels


async def test_selection_is_stored_and_resolved(hass: HomeAssistant) -> None:
    """Selecting a runnable stores it in options and resolves it after the reload."""
    entry = await _setup_entry(hass)

    with patched_client():
        result = await _open_selection(hass, entry)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {OPT_RUNNABLES: ["script:u/automation/lights"]}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[OPT_RUNNABLES] == [LIGHTS_SELECTION]
    assert entry.options[OPT_INSTANCE_HEALTH] is False
    resolved = entry.runtime_data.runnable_coordinator.data[("script", "u/automation/lights")]
    assert resolved.available is True
    assert resolved.executable is True
    assert resolved.details.script_hash == "0123456789abcdef"


async def test_pinning_applies_only_to_new_selections(hass: HomeAssistant) -> None:
    """An existing selection keeps its addressing mode when the pin box is ticked."""
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]})

    with patched_client():
        result = await _open_selection(hass, entry)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                OPT_RUNNABLES: ["script:u/automation/lights", "flow:f/home/night"],
                "pin_selected": True,
            },
        )
        await hass.async_block_till_done()

    stored = {item["path"]: item["mode"] for item in entry.options[OPT_RUNNABLES]}
    assert stored == {"u/automation/lights": "latest", "f/home/night": "pinned"}


async def test_selection_survives_reload_and_order_changes(hass: HomeAssistant) -> None:
    """Selection is keyed by kind and path, not by discovery order."""
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]})

    with patched_client(runnables=(NIGHT, LIGHTS)):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        result = await _open_selection(hass, entry)

    assert entry.options[OPT_RUNNABLES] == [LIGHTS_SELECTION]
    marker = next(iter(result["data_schema"].schema))
    assert marker.default() == ["script:u/automation/lights"]
    assert entry.runtime_data.runnable_coordinator.data[("script", "u/automation/lights")].available


@pytest.mark.parametrize(
    ("error", "reason"),
    [(WindmillNotFoundError(), "missing"), (WindmillAuthorizationError(), "unauthorized")],
)
async def test_removed_or_denied_runnable_is_unavailable(
    hass: HomeAssistant, error: Exception, reason: str
) -> None:
    """A removed or inaccessible runnable stays selected but is not executable."""
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]}, details=error)

    assert entry.state is ConfigEntryState.LOADED
    resolved = entry.runtime_data.runnable_coordinator.data[("script", "u/automation/lights")]
    assert resolved.available is False
    assert resolved.reason == reason
    assert resolved.executable is False


async def test_unavailable_runnable_recovers(hass: HomeAssistant) -> None:
    """A runnable that returns becomes available again without user action."""
    entry = await _setup_entry(
        hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]}, details=WindmillNotFoundError()
    )

    with patched_client():
        await entry.runtime_data.runnable_coordinator.async_refresh()
        await hass.async_block_till_done()

    assert entry.runtime_data.runnable_coordinator.data[("script", "u/automation/lights")].available


async def test_unsupported_schema_blocks_execution(hass: HomeAssistant) -> None:
    """An unsupported argument schema is identified before execution is enabled."""
    entry = await _setup_entry(
        hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]}, details=UNSUPPORTED_DETAILS
    )

    resolved = entry.runtime_data.runnable_coordinator.data[("script", "u/automation/lights")]
    assert resolved.available is True
    assert resolved.executable is False
    assert resolved.reason == "unsupported_parameter_type"


async def test_temporary_resolution_failure_fails_setup(hass: HomeAssistant) -> None:
    """A transient failure retries instead of dropping the selection."""
    entry = await _setup_entry(
        hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]}, details=WindmillConnectionError()
    )

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.options[OPT_RUNNABLES] == [LIGHTS_SELECTION]


async def test_denied_discovery_keeps_existing_selection_visible(hass: HomeAssistant) -> None:
    """A denied listing still shows what is already selected."""
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]})

    with patched_client(runnables=WindmillAuthorizationError()):
        result = await _open_selection(hass, entry)

    selector = next(iter(result["data_schema"].schema.values()))
    assert [option["value"] for option in selector.config["options"]] == [
        "script:u/automation/lights"
    ]


async def test_too_many_runnables_are_rejected(hass: HomeAssistant) -> None:
    """The selection stays bounded so large workspaces cannot be exposed wholesale."""
    bulk = tuple(
        WindmillRunnable(kind=RunnableKind.SCRIPT, path=f"u/bulk/job{index}", summary="")
        for index in range(MAX_SELECTED_RUNNABLES + 1)
    )
    entry = await _setup_entry(hass, runnables=bulk)

    with patched_client(runnables=bulk):
        result = await _open_selection(hass, entry)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {OPT_RUNNABLES: [f"script:{runnable.path}" for runnable in bulk]},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {OPT_RUNNABLES: "too_many_runnables"}
    assert entry.options.get(OPT_RUNNABLES) is None


async def test_unsupported_discovery_capability_skips_resolution(hass: HomeAssistant) -> None:
    """Without discovery permission no runnable coordinator is created."""
    entry = await _setup_entry(
        hass,
        options={OPT_RUNNABLES: [LIGHTS_SELECTION]},
        capabilities=_capabilities(script_discovery=UNAUTHORIZED, flow_discovery=UNAUTHORIZED),
    )

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.runnable_coordinator is None


def test_stored_selection_parsing_is_defensive() -> None:
    """Unreadable, duplicated and unsafe stored selections are discarded."""
    selections = load_selections(
        [
            LIGHTS_SELECTION,
            LIGHTS_SELECTION,
            {"kind": "script", "path": "../etc/passwd", "mode": "latest"},
            {"kind": "mystery", "path": "u/a/b", "mode": "latest"},
            {"kind": "flow", "path": "f/home/night", "mode": "mystery"},
            "not-a-selection",
        ]
    )

    assert selections == (
        RunnableSelection(
            kind=RunnableKind.SCRIPT,
            path="u/automation/lights",
            mode=AddressingMode.LATEST,
        ),
    )
    assert load_selections("not-a-list") == ()
