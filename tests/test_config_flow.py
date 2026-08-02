"""Tests for the Windmill configuration flows through Home Assistant interfaces."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import SelectSelector, TextSelector
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.windmill.api import (
    CapabilityAvailability,
    CapabilityMatrix,
    CapabilityReason,
    CapabilityStatus,
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillConnection,
    WindmillConnectionError,
    WindmillDetailedHealth,
    WindmillEdition,
    WindmillHealthState,
    WindmillHealthStatus,
    WindmillIdentity,
    WindmillNotFoundError,
    WindmillProtocolError,
    WindmillRateLimitError,
    WindmillRequestError,
    WindmillServerError,
    WindmillServerInfo,
    WindmillTimeoutError,
    WindmillWorkspaceError,
    WindmillWorkspaceInfo,
)
from custom_components.windmill.const import (
    CONF_BASE_URL,
    CONF_TOKEN,
    CONF_WORKSPACE,
    DOMAIN,
    OPT_DETAILED_HEALTH,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
    OPT_UPDATE_ENTITY,
    OPT_WORKER_DETAILS,
    OPT_WORKER_GROUPS,
)

TOKEN = "obviously-fake-test-token"
ROTATED_TOKEN = "rotated-obviously-fake-token"
CONNECTION_INPUT = {CONF_BASE_URL: "https://windmill.example/", CONF_TOKEN: TOKEN}
WORKSPACE = "home-assistant"
ENTRY_DATA = {
    CONF_BASE_URL: "https://windmill.example",
    CONF_WORKSPACE: WORKSPACE,
    CONF_TOKEN: TOKEN,
}
WORKSPACES = (
    WindmillWorkspaceInfo(id=WORKSPACE, name="Home Assistant"),
    WindmillWorkspaceInfo(id="admin", name="Admin"),
)
SERVER = WindmillServerInfo(edition=WindmillEdition.COMMUNITY, version="v1.775.2")
HEALTH = WindmillHealthStatus(
    status=WindmillHealthState.HEALTHY,
    checked_at=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
    database_healthy=True,
    workers_alive=2,
)
DETAILED_HEALTH = WindmillDetailedHealth(
    status=WindmillHealthState.HEALTHY,
    checked_at=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
    database_healthy=True,
    workers_alive=2,
    pending_jobs=1,
    running_jobs=0,
)
IDENTITY = WindmillIdentity(username="automation", is_admin=False, is_super_admin=False)
CONNECTION = WindmillConnection(identity=IDENTITY, server=SERVER)

AVAILABLE = CapabilityAvailability(CapabilityStatus.AVAILABLE, CapabilityReason.PROBE_SUCCEEDED)
UNAUTHORIZED = CapabilityAvailability(
    CapabilityStatus.UNAUTHORIZED, CapabilityReason.PERMISSION_DENIED
)
UNSUPPORTED = CapabilityAvailability(
    CapabilityStatus.UNSUPPORTED, CapabilityReason.ENDPOINT_MISSING
)
CONTEXT_REQUIRED = CapabilityAvailability(
    CapabilityStatus.NOT_APPLICABLE, CapabilityReason.CONTEXT_REQUIRED
)
FULL_CAPABILITIES = CapabilityMatrix(
    health=AVAILABLE,
    detailed_health=AVAILABLE,
    workers=AVAILABLE,
    runs=AVAILABLE,
    script_discovery=AVAILABLE,
    flow_discovery=AVAILABLE,
    script_execution=CONTEXT_REQUIRED,
    flow_execution=CONTEXT_REQUIRED,
    cancellation=CONTEXT_REQUIRED,
    update_visibility=AVAILABLE,
)
RESTRICTED_CAPABILITIES = CapabilityMatrix(
    health=AVAILABLE,
    detailed_health=UNAUTHORIZED,
    workers=UNAUTHORIZED,
    runs=AVAILABLE,
    script_discovery=AVAILABLE,
    flow_discovery=UNSUPPORTED,
    script_execution=CONTEXT_REQUIRED,
    flow_execution=CONTEXT_REQUIRED,
    cancellation=CONTEXT_REQUIRED,
    update_visibility=UNSUPPORTED,
)
ALL_FEATURES_OFF = {
    OPT_INSTANCE_HEALTH: False,
    OPT_DETAILED_HEALTH: False,
    OPT_WORKER_GROUPS: False,
    OPT_WORKER_DETAILS: False,
    OPT_RUN_OBSERVATION: False,
    OPT_UPDATE_ENTITY: False,
}


def _as_mock(value: Any) -> AsyncMock:
    """Return an asynchronous mock returning or raising the supplied value."""
    if isinstance(value, Exception):
        return AsyncMock(side_effect=value)
    return AsyncMock(return_value=value)


@contextmanager
def patched_client(
    *,
    server: Any = SERVER,
    workspaces: Any = WORKSPACES,
    connection: Any = CONNECTION,
    capabilities: Any = FULL_CAPABILITIES,
    health: Any = HEALTH,
    detailed: Any = DETAILED_HEALTH,
    workers: Any = (),
    worker_groups: Any = (),
    jobs: Any = (),
) -> Iterator[dict[str, AsyncMock]]:
    """Patch every network operation the flows may perform."""
    mocks = {
        "server": _as_mock(server),
        "workspaces": _as_mock(workspaces),
        "connect": _as_mock(connection),
        "capabilities": _as_mock(capabilities),
        "health": _as_mock(health),
        "detailed": _as_mock(detailed),
        "workers": _as_mock(workers),
        "worker_groups": _as_mock(worker_groups),
        "jobs": _as_mock(jobs),
    }
    targets = {
        "server": "custom_components.windmill.api.WindmillInstanceClient.async_get_server_info",
        "workspaces": "custom_components.windmill.api.WindmillInstanceClient.async_list_workspaces",
        "connect": "custom_components.windmill.api.WindmillClient.async_connect",
        "capabilities": "custom_components.windmill.api.WindmillClient.async_discover_capabilities",
        "health": "custom_components.windmill.api.WindmillInstanceClient.async_get_health_status",
        "detailed": (
            "custom_components.windmill.api.WindmillInstanceClient.async_get_detailed_health"
        ),
        "workers": "custom_components.windmill.api.WindmillInstanceClient.async_list_workers",
        "worker_groups": (
            "custom_components.windmill.api.WindmillInstanceClient.async_list_worker_groups"
        ),
        "jobs": "custom_components.windmill.api.WindmillClient.async_list_jobs",
    }
    with ExitStack() as stack:
        for key, target in targets.items():
            stack.enter_context(patch(target, new=mocks[key]))
        yield mocks


async def _start_connection_step(hass: HomeAssistant, user_input: dict[str, str]) -> Any:
    """Start the user flow and submit the connection step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


def _schema_fields(result: Any) -> dict[str, Any]:
    """Return the submitted schema of a form result keyed by field name."""
    return {marker.schema: validator for marker, validator in result["data_schema"].schema.items()}


async def test_connection_step_form(hass: HomeAssistant) -> None:
    """Onboarding starts with connection details only."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    fields = _schema_fields(result)
    assert set(fields) == {CONF_BASE_URL, CONF_TOKEN}
    assert isinstance(fields[CONF_TOKEN], TextSelector)
    assert fields[CONF_TOKEN].config["type"] == "password"


async def test_guided_onboarding_creates_entry(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """The assistant guides connection, workspace, capabilities and features."""
    with patched_client() as mocks:
        result = await _start_connection_step(hass, CONNECTION_INPUT)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "workspace"
        assert isinstance(_schema_fields(result)[CONF_WORKSPACE], SelectSelector)
        mocks["connect"].assert_not_awaited()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_WORKSPACE: WORKSPACE}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "capabilities"
        assert result["description_placeholders"] == {
            "server": "CE v1.775.2",
            "username": "automation",
            "workspace": WORKSPACE,
            "health": "available",
            "detailed_health": "available",
            "workers": "available",
            "runs": "available",
            "script_discovery": "available",
            "flow_discovery": "available",
            "update_visibility": "available",
        }

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["step_id"] == "features"
        defaults = {
            marker.schema: marker.default()
            for marker in result["data_schema"].schema
            if marker.default is not None
        }
        assert defaults == {
            OPT_INSTANCE_HEALTH: True,
            OPT_DETAILED_HEALTH: False,
            OPT_WORKER_GROUPS: False,
            OPT_WORKER_DETAILS: False,
            OPT_RUN_OBSERVATION: True,
            OPT_UPDATE_ENTITY: False,
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                OPT_INSTANCE_HEALTH: True,
                OPT_DETAILED_HEALTH: True,
                OPT_WORKER_GROUPS: False,
                OPT_WORKER_DETAILS: False,
                OPT_RUN_OBSERVATION: True,
                OPT_UPDATE_ENTITY: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == WORKSPACE
    assert result["data"] == ENTRY_DATA
    assert result["options"] == {
        OPT_INSTANCE_HEALTH: True,
        OPT_DETAILED_HEALTH: True,
        OPT_WORKER_GROUPS: False,
        OPT_WORKER_DETAILS: False,
        OPT_RUN_OBSERVATION: True,
        OPT_UPDATE_ENTITY: False,
    }
    assert TOKEN not in caplog.text


async def test_restricted_token_uses_manual_workspace_entry(hass: HomeAssistant) -> None:
    """A token without workspace listing permission can still finish onboarding."""
    with patched_client(
        workspaces=WindmillAuthorizationError(), capabilities=RESTRICTED_CAPABILITIES
    ):
        result = await _start_connection_step(hass, CONNECTION_INPUT)

        assert result["step_id"] == "workspace"
        assert _schema_fields(result)[CONF_WORKSPACE] is str

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_WORKSPACE: WORKSPACE}
        )

        assert result["step_id"] == "capabilities"
        assert result["description_placeholders"]["workers"] == "unauthorized"
        assert result["description_placeholders"]["flow_discovery"] == "unsupported"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        defaults = {
            marker.schema: marker.default()
            for marker in result["data_schema"].schema
            if marker.default is not None
        }
        assert defaults[OPT_INSTANCE_HEALTH] is True
        assert defaults[OPT_RUN_OBSERVATION] is True
        assert defaults[OPT_DETAILED_HEALTH] is False
        assert defaults[OPT_WORKER_DETAILS] is False
        assert defaults[OPT_UPDATE_ENTITY] is False

        result = await hass.config_entries.flow.async_configure(result["flow_id"], ALL_FEATURES_OFF)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == ENTRY_DATA


@pytest.mark.parametrize(
    ("error", "field", "error_key"),
    [
        (WindmillAuthenticationError(), CONF_TOKEN, "invalid_auth"),
        (WindmillConnectionError(), "base", "cannot_connect"),
        (WindmillTimeoutError(), "base", "cannot_connect"),
        (WindmillRateLimitError(), "base", "server_error"),
        (WindmillServerError(), "base", "server_error"),
        (WindmillProtocolError(), "base", "unexpected_response"),
        (WindmillRequestError(), "base", "unexpected_response"),
    ],
)
async def test_connection_step_error_mapping(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    field: str,
    error_key: str,
) -> None:
    """Instance validation failures stay user-distinct and keep the user in step one."""
    with patched_client(server=error) as mocks:
        result = await _start_connection_step(hass, CONNECTION_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {field: error_key}
    mocks["workspaces"].assert_not_awaited()
    assert TOKEN not in caplog.text


@pytest.mark.parametrize(
    ("error", "field", "error_key"),
    [
        (WindmillAuthenticationError(), CONF_TOKEN, "invalid_auth"),
        (WindmillConnectionError(), "base", "cannot_connect"),
        (WindmillServerError(), "base", "server_error"),
    ],
)
async def test_workspace_listing_transport_errors_stay_in_connection_step(
    hass: HomeAssistant, error: Exception, field: str, error_key: str
) -> None:
    """Only permission and contract failures fall back to manual workspace entry."""
    with patched_client(workspaces=error):
        result = await _start_connection_step(hass, CONNECTION_INPUT)

    assert result["step_id"] == "user"
    assert result["errors"] == {field: error_key}


@pytest.mark.parametrize(
    "error",
    [
        WindmillAuthorizationError(),
        WindmillNotFoundError(),
        WindmillProtocolError(),
        WindmillRequestError(),
    ],
)
async def test_workspace_listing_degrades_to_manual_entry(
    hass: HomeAssistant, error: Exception
) -> None:
    """A missing or denied workspace listing never blocks onboarding."""
    with patched_client(workspaces=error):
        result = await _start_connection_step(hass, CONNECTION_INPUT)

    assert result["step_id"] == "workspace"
    assert _schema_fields(result)[CONF_WORKSPACE] is str


@pytest.mark.parametrize(
    ("connection_input", "expected_errors"),
    [
        ({CONF_BASE_URL: "http://windmill.example"}, {CONF_BASE_URL: "invalid_url"}),
        ({CONF_BASE_URL: "https://user:pw@windmill.example"}, {CONF_BASE_URL: "invalid_url"}),
        ({CONF_TOKEN: ""}, {CONF_TOKEN: "invalid_auth"}),
    ],
)
async def test_connection_step_rejects_unsafe_input_locally(
    hass: HomeAssistant,
    connection_input: dict[str, str],
    expected_errors: dict[str, str],
) -> None:
    """Unsafe URLs and empty credentials fail before any request is made."""
    with patched_client() as mocks:
        result = await _start_connection_step(hass, {**CONNECTION_INPUT, **connection_input})

    assert result["step_id"] == "user"
    assert result["errors"] == expected_errors
    mocks["server"].assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "field", "error_key"),
    [
        (WindmillAuthenticationError(), CONF_TOKEN, "invalid_auth"),
        (WindmillAuthorizationError(), CONF_TOKEN, "insufficient_permission"),
        (WindmillWorkspaceError(), CONF_WORKSPACE, "invalid_workspace"),
        (WindmillConnectionError(), "base", "cannot_connect"),
        (WindmillServerError(), "base", "server_error"),
        (WindmillProtocolError(), "base", "unexpected_response"),
    ],
)
async def test_workspace_step_error_mapping(
    hass: HomeAssistant, error: Exception, field: str, error_key: str
) -> None:
    """Workspace validation failures keep the user in the workspace step."""
    with patched_client(connection=error):
        result = await _start_connection_step(hass, CONNECTION_INPUT)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_WORKSPACE: WORKSPACE}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "workspace"
    assert result["errors"] == {field: error_key}


async def test_workspace_step_rejects_invalid_workspace_locally(hass: HomeAssistant) -> None:
    """An unusable workspace identifier fails before the whoami request."""
    with patched_client() as mocks:
        result = await _start_connection_step(hass, CONNECTION_INPUT)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_WORKSPACE: "\x00"}
        )

    assert result["errors"] == {CONF_WORKSPACE: "invalid_workspace"}
    mocks["connect"].assert_not_awaited()


async def test_capability_discovery_failure_is_reported(hass: HomeAssistant) -> None:
    """A failing capability probe reports an error instead of creating an entry."""
    with patched_client(capabilities=WindmillAuthenticationError()):
        result = await _start_connection_step(hass, CONNECTION_INPUT)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_WORKSPACE: WORKSPACE}
        )

    assert result["step_id"] == "workspace"
    assert result["errors"] == {CONF_TOKEN: "invalid_auth"}


@pytest.mark.parametrize(
    ("existing_base_url", "submitted_base_url"),
    [
        ("https://windmill.example", "HTTPS://WINDMILL.EXAMPLE:443/"),
        ("https://windmill.example/root", "https://windmill.example/%72oot"),
    ],
)
async def test_duplicate_identity_is_rejected(
    hass: HomeAssistant, existing_base_url: str, submitted_base_url: str
) -> None:
    """Equivalent canonical instance and workspace pairs abort the assistant."""
    MockConfigEntry(
        domain=DOMAIN,
        title=WORKSPACE,
        data={**ENTRY_DATA, CONF_BASE_URL: existing_base_url, CONF_TOKEN: "other-fake-token"},
    ).add_to_hass(hass)

    with patched_client() as mocks:
        result = await _start_connection_step(
            hass, {**CONNECTION_INPUT, CONF_BASE_URL: submitted_base_url}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_WORKSPACE: WORKSPACE}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mocks["connect"].assert_not_awaited()


async def _add_loaded_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add and set up a loaded Windmill entry with default options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=WORKSPACE,
        data=ENTRY_DATA,
        options={
            OPT_INSTANCE_HEALTH: True,
            OPT_DETAILED_HEALTH: False,
            OPT_WORKER_GROUPS: False,
            OPT_WORKER_DETAILS: False,
            OPT_RUN_OBSERVATION: True,
            OPT_UPDATE_ENTITY: False,
        },
    )
    entry.add_to_hass(hass)
    with patched_client():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_reauth_updates_token_and_reloads(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Reauthentication replaces only the credential and reloads the entry."""
    entry = await _add_loaded_entry(hass)

    with patched_client() as mocks:
        result = await entry.start_reauth_flow(hass)

        assert result["step_id"] == "reauth_confirm"
        placeholders = result["description_placeholders"]
        assert placeholders[CONF_BASE_URL] == ENTRY_DATA[CONF_BASE_URL]
        assert placeholders[CONF_WORKSPACE] == WORKSPACE
        assert TOKEN not in str(placeholders)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: ROTATED_TOKEN}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {**ENTRY_DATA, CONF_TOKEN: ROTATED_TOKEN}
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert mocks["connect"].await_count == 2
    assert ROTATED_TOKEN not in caplog.text


async def test_reauth_failure_keeps_stored_token(hass: HomeAssistant) -> None:
    """A rejected credential leaves the stored identity and token untouched."""
    entry = await _add_loaded_entry(hass)

    with patched_client(connection=WindmillAuthenticationError()):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: ROTATED_TOKEN}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_TOKEN: "invalid_auth"}
    assert entry.data == ENTRY_DATA


async def test_reconfigure_updates_identity_and_keeps_token(hass: HomeAssistant) -> None:
    """Reconfiguration may change identity and keeps the stored token when empty."""
    entry = await _add_loaded_entry(hass)

    with patched_client():
        result = await entry.start_reconfigure_flow(hass)

        assert result["step_id"] == "reconfigure"
        fields = _schema_fields(result)
        assert set(fields) == {CONF_BASE_URL, CONF_WORKSPACE, CONF_TOKEN}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BASE_URL: "https://windmill.example/", CONF_WORKSPACE: "production"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_BASE_URL: "https://windmill.example",
        CONF_WORKSPACE: "production",
        CONF_TOKEN: TOKEN,
    }
    assert entry.title == WORKSPACE
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_reconfigure_replaces_token_when_supplied(hass: HomeAssistant) -> None:
    """A supplied reconfiguration token replaces the stored credential."""
    entry = await _add_loaded_entry(hass)

    with patched_client():
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: ENTRY_DATA[CONF_BASE_URL],
                CONF_WORKSPACE: WORKSPACE,
                CONF_TOKEN: ROTATED_TOKEN,
            },
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {**ENTRY_DATA, CONF_TOKEN: ROTATED_TOKEN}


async def test_reconfigure_rejects_another_entrys_identity(hass: HomeAssistant) -> None:
    """Reconfiguration cannot collide with an already configured identity."""
    entry = await _add_loaded_entry(hass)
    MockConfigEntry(
        domain=DOMAIN,
        title="production",
        data={**ENTRY_DATA, CONF_WORKSPACE: "production", CONF_TOKEN: "other-fake-token"},
    ).add_to_hass(hass)

    with patched_client() as mocks:
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BASE_URL: ENTRY_DATA[CONF_BASE_URL], CONF_WORKSPACE: "production"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == ENTRY_DATA
    mocks["connect"].assert_not_awaited()


@pytest.mark.parametrize(
    ("user_input", "expected_errors"),
    [
        ({CONF_BASE_URL: "http://windmill.example"}, {CONF_BASE_URL: "invalid_url"}),
        ({CONF_WORKSPACE: "\x00"}, {CONF_WORKSPACE: "invalid_workspace"}),
    ],
)
async def test_reconfigure_rejects_unsafe_input(
    hass: HomeAssistant, user_input: dict[str, str], expected_errors: dict[str, str]
) -> None:
    """Reconfiguration applies the same local safety rules as onboarding."""
    entry = await _add_loaded_entry(hass)

    with patched_client() as mocks:
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: ENTRY_DATA[CONF_BASE_URL],
                CONF_WORKSPACE: WORKSPACE,
                **user_input,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_errors
    assert entry.data == ENTRY_DATA
    mocks["connect"].assert_not_awaited()


async def test_reconfigure_reports_connection_failure(hass: HomeAssistant) -> None:
    """A failing reconfiguration leaves the entry data unchanged."""
    entry = await _add_loaded_entry(hass)

    with patched_client(connection=WindmillConnectionError()):
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BASE_URL: "https://other.example", CONF_WORKSPACE: WORKSPACE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == ENTRY_DATA


async def test_options_flow_updates_features_and_reloads(hass: HomeAssistant) -> None:
    """Feature options can be changed later without touching identity."""
    entry = await _add_loaded_entry(hass)

    with patched_client() as mocks:
        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] is FlowResultType.MENU
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "features"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "features"
        defaults = {
            marker.schema: marker.default()
            for marker in result["data_schema"].schema
            if marker.default is not None
        }
        assert defaults == entry.options

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                OPT_INSTANCE_HEALTH: True,
                OPT_DETAILED_HEALTH: True,
                OPT_WORKER_GROUPS: True,
                OPT_WORKER_DETAILS: True,
                OPT_RUN_OBSERVATION: False,
                OPT_UPDATE_ENTITY: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        OPT_INSTANCE_HEALTH: True,
        OPT_DETAILED_HEALTH: True,
        OPT_WORKER_GROUPS: True,
        OPT_WORKER_DETAILS: True,
        OPT_RUN_OBSERVATION: False,
        OPT_UPDATE_ENTITY: False,
    }
    assert entry.data == ENTRY_DATA
    assert entry.state is config_entries.ConfigEntryState.LOADED
    # The single connect inside this patch context proves the automatic reload ran.
    assert mocks["connect"].await_count == 1


async def test_options_flow_defaults_for_legacy_entry(hass: HomeAssistant) -> None:
    """An entry created before feature options falls back to safe defaults."""
    entry = MockConfigEntry(domain=DOMAIN, title=WORKSPACE, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    with patched_client():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "features"}
        )

    defaults = {
        marker.schema: marker.default()
        for marker in result["data_schema"].schema
        if marker.default is not None
    }
    assert defaults == {
        OPT_INSTANCE_HEALTH: True,
        OPT_DETAILED_HEALTH: False,
        OPT_WORKER_GROUPS: False,
        OPT_WORKER_DETAILS: False,
        OPT_RUN_OBSERVATION: True,
        OPT_UPDATE_ENTITY: False,
    }
