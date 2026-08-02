"""Tests for Windmill execution actions and optional runnable buttons."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.windmill.api import (
    AddressingMode,
    RunnableDetails,
    RunnableKind,
    RunnableParameter,
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillConnectionError,
    WindmillNotFoundError,
    WindmillProtocolError,
)
from custom_components.windmill.const import (
    ATTR_ARGUMENTS,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_KIND,
    ATTR_PATH,
    DOMAIN,
    OPT_RUNNABLE_BUTTONS,
    OPT_RUNNABLES,
)
from tests.test_health import ENTRY_DATA, WORKSPACE
from tests.test_runnables import (
    BASE_OPTIONS,
    LIGHTS_DETAILS,
    LIGHTS_SELECTION,
    UNSUPPORTED_DETAILS,
    _setup_entry,
    patched_client,
)

JOB_ID = "00000000-0000-4000-8000-00000000000a"
NIGHT_SELECTION = {"kind": "flow", "path": "f/home/night", "mode": AddressingMode.PINNED.value}
NIGHT_DETAILS = RunnableDetails(
    kind=RunnableKind.FLOW,
    path="f/home/night",
    summary="Night",
    script_hash=None,
    flow_version=7,
    parameters=(),
    schema_supported=True,
)
PINNED_LIGHTS = {**LIGHTS_SELECTION, "mode": AddressingMode.PINNED.value}
PARAMETERLESS_LIGHTS = RunnableDetails(
    kind=RunnableKind.SCRIPT,
    path="u/automation/lights",
    summary="Toggle the lights",
    script_hash="0123456789abcdef",
    flow_version=None,
    parameters=(),
    schema_supported=True,
)


async def _run(hass: HomeAssistant, entry: MockConfigEntry, **overrides: Any) -> Any:
    """Call the run action with sensible defaults."""
    data = {
        ATTR_CONFIG_ENTRY_ID: entry.entry_id,
        ATTR_KIND: "script",
        ATTR_PATH: "u/automation/lights",
        ATTR_ARGUMENTS: {"room": "kitchen"},
        **overrides,
    }
    return await hass.services.async_call(DOMAIN, "run", data, blocking=True, return_response=True)


async def test_selected_runnable_starts_and_returns_job_id(hass: HomeAssistant) -> None:
    """A selected script starts asynchronously and returns only bounded metadata."""
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]})

    with patch(
        "custom_components.windmill.api.WindmillClient.async_run_runnable",
        new=AsyncMock(return_value=JOB_ID),
    ) as run:
        response = await _run(hass, entry)

    assert response == {"job_id": JOB_ID}
    assert run.await_args.args[:2] == (RunnableKind.SCRIPT, "u/automation/lights")
    assert run.await_args.args[2] == {"room": "kitchen"}
    assert run.await_args.kwargs == {"script_hash": None, "flow_version": None}


async def test_pinned_selection_addresses_hash_or_version(hass: HomeAssistant) -> None:
    """A pinned selection is addressed by hash or version, never by the deployed head."""
    entry = await _setup_entry(
        hass, options={OPT_RUNNABLES: [PINNED_LIGHTS, NIGHT_SELECTION]}, details=LIGHTS_DETAILS
    )

    with patch(
        "custom_components.windmill.api.WindmillClient.async_run_runnable",
        new=AsyncMock(return_value=JOB_ID),
    ) as run:
        await _run(hass, entry)

    assert run.await_args.kwargs == {"script_hash": "0123456789abcdef", "flow_version": None}


async def test_unselected_runnable_cannot_be_executed(hass: HomeAssistant) -> None:
    """A runnable that was never selected is rejected before any request."""
    entry = await _setup_entry(hass)

    with (
        patch(
            "custom_components.windmill.api.WindmillClient.async_run_runnable",
            new=AsyncMock(return_value=JOB_ID),
        ) as run,
        pytest.raises(ServiceValidationError),
    ):
        await _run(hass, entry)

    run.assert_not_awaited()


async def test_unavailable_runnable_is_rejected(hass: HomeAssistant) -> None:
    """A selected but missing runnable is rejected locally."""
    entry = await _setup_entry(
        hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]}, details=WindmillNotFoundError()
    )

    with pytest.raises(ServiceValidationError):
        await _run(hass, entry)


async def test_unsupported_schema_blocks_execution(hass: HomeAssistant) -> None:
    """A runnable with an unsupported schema cannot be executed."""
    entry = await _setup_entry(
        hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]}, details=UNSUPPORTED_DETAILS
    )

    with pytest.raises(ServiceValidationError):
        await _run(hass, entry)


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"room": "kitchen", "extra": 1},
        {"room": 42},
        {"room": "garage"},
        {"room": "x" * 9000},
    ],
)
async def test_invalid_arguments_fail_before_the_request(
    hass: HomeAssistant, arguments: dict[str, Any]
) -> None:
    """Missing, unknown, mistyped, out-of-enum and oversized arguments fail locally."""
    details = RunnableDetails(
        kind=RunnableKind.SCRIPT,
        path="u/automation/lights",
        summary="",
        script_hash="0123456789abcdef",
        flow_version=None,
        parameters=(
            RunnableParameter(name="room", type="string", required=True, enum=("kitchen", "hall")),
        ),
        schema_supported=True,
    )
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]}, details=details)

    with (
        patch(
            "custom_components.windmill.api.WindmillClient.async_run_runnable",
            new=AsyncMock(return_value=JOB_ID),
        ) as run,
        pytest.raises(ServiceValidationError),
    ):
        await _run(hass, entry, **{ATTR_ARGUMENTS: arguments})

    run.assert_not_awaited()


async def test_boolean_is_not_accepted_as_a_number(hass: HomeAssistant) -> None:
    """A boolean never satisfies a numeric parameter."""
    details = RunnableDetails(
        kind=RunnableKind.SCRIPT,
        path="u/automation/lights",
        summary="",
        script_hash=None,
        flow_version=None,
        parameters=(RunnableParameter(name="level", type="integer", required=False),),
        schema_supported=True,
    )
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]}, details=details)

    with pytest.raises(ServiceValidationError):
        await _run(hass, entry, **{ATTR_ARGUMENTS: {"level": True}})


@pytest.mark.parametrize(
    "error",
    [
        WindmillAuthenticationError(),
        WindmillAuthorizationError(),
        WindmillNotFoundError(),
        WindmillConnectionError(),
        WindmillProtocolError(),
    ],
)
async def test_execution_failures_stay_distinguishable(
    hass: HomeAssistant, error: Exception
) -> None:
    """Every client failure class becomes a distinct user-facing error."""
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]})

    with (
        patch(
            "custom_components.windmill.api.WindmillClient.async_run_runnable",
            new=AsyncMock(side_effect=error),
        ),
        pytest.raises(HomeAssistantError) as caught,
    ):
        await _run(hass, entry)

    assert caught.value.translation_key in {
        "invalid_auth",
        "insufficient_permission",
        "runnable_missing",
        "cannot_connect",
        "unexpected_response",
    }


async def test_unknown_or_unloaded_entry_is_rejected(hass: HomeAssistant) -> None:
    """The action refuses unknown and unloaded config entries."""
    entry = MockConfigEntry(domain=DOMAIN, title=WORKSPACE, data=ENTRY_DATA, options=BASE_OPTIONS)
    entry.add_to_hass(hass)

    with pytest.raises(ServiceValidationError):
        await _run(hass, entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "run",
            {
                ATTR_CONFIG_ENTRY_ID: "does-not-exist",
                ATTR_KIND: "script",
                ATTR_PATH: "u/automation/lights",
            },
            blocking=True,
            return_response=True,
        )


async def test_buttons_are_opt_in(hass: HomeAssistant) -> None:
    """Parameterless buttons appear only after the user enables them."""
    entry = await _setup_entry(
        hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]}, details=PARAMETERLESS_LIGHTS
    )

    assert hass.states.async_entity_ids("button") == []

    with patched_client(details=PARAMETERLESS_LIGHTS):
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, OPT_RUNNABLE_BUTTONS: True},
        )
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.async_entity_ids("button") == [
        "button.home_assistant_run_u_automation_lights"
    ]


async def test_button_press_starts_the_runnable(hass: HomeAssistant) -> None:
    """Pressing a button starts the runnable without arguments."""
    entry = await _setup_entry(
        hass,
        options={OPT_RUNNABLES: [LIGHTS_SELECTION], OPT_RUNNABLE_BUTTONS: True},
        details=PARAMETERLESS_LIGHTS,
    )

    with patch(
        "custom_components.windmill.api.WindmillClient.async_run_runnable",
        new=AsyncMock(return_value=JOB_ID),
    ) as run:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.home_assistant_run_u_automation_lights"},
            blocking=True,
        )

    assert run.await_args.args[2] == {}
    assert entry.state.name == "LOADED"


async def test_runnable_with_parameters_gets_no_button(hass: HomeAssistant) -> None:
    """A runnable that needs arguments is only reachable through the action."""
    await _setup_entry(
        hass,
        options={OPT_RUNNABLES: [LIGHTS_SELECTION], OPT_RUNNABLE_BUTTONS: True},
        details=LIGHTS_DETAILS,
    )

    assert hass.states.async_entity_ids("button") == []


async def test_pinned_flow_without_version_is_refused(hass: HomeAssistant) -> None:
    """A pinned runnable that Windmill cannot pin is refused instead of running latest."""
    unpinnable = RunnableDetails(
        kind=RunnableKind.FLOW,
        path="f/home/night",
        summary="Night",
        script_hash=None,
        flow_version=None,
        parameters=(),
        schema_supported=True,
    )
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [NIGHT_SELECTION]}, details=unpinnable)

    with (
        patch(
            "custom_components.windmill.api.WindmillClient.async_run_runnable",
            new=AsyncMock(return_value=JOB_ID),
        ) as run,
        pytest.raises(ServiceValidationError) as caught,
    ):
        await _run(
            hass, entry, **{ATTR_KIND: "flow", ATTR_PATH: "f/home/night", ATTR_ARGUMENTS: {}}
        )

    assert caught.value.translation_key == "pin_unavailable"
    run.assert_not_awaited()


async def test_non_serializable_arguments_are_refused(hass: HomeAssistant) -> None:
    """Arguments that are not JSON-compatible never reach the network layer."""
    entry = await _setup_entry(hass, options={OPT_RUNNABLES: [LIGHTS_SELECTION]})

    with pytest.raises(ServiceValidationError) as caught:
        await _run(hass, entry, **{ATTR_ARGUMENTS: {"room": {"kitchen"}}})

    assert caught.value.translation_key == "invalid_arguments"
