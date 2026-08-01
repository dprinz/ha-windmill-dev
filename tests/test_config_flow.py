"""Tests for the Windmill config flow through Home Assistant interfaces."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import TextSelector
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.windmill.api import (
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillConnectionError,
    WindmillIdentity,
    WindmillProtocolError,
    WindmillRateLimitError,
    WindmillRequestError,
    WindmillServerError,
    WindmillTimeoutError,
    WindmillWorkspaceError,
)
from custom_components.windmill.const import (
    CONF_BASE_URL,
    CONF_TOKEN,
    CONF_WORKSPACE,
    DOMAIN,
)

USER_INPUT = {
    CONF_BASE_URL: "https://windmill.example/",
    CONF_WORKSPACE: "home-assistant",
    CONF_TOKEN: "obviously-fake-test-token",
}
IDENTITY = WindmillIdentity(username="automation", is_admin=False, is_super_admin=False)


async def _start_user_flow(hass: HomeAssistant, data: dict[str, str]) -> dict:
    """Start the public user flow with the supplied data."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=data,
    )


async def test_user_form(hass: HomeAssistant) -> None:
    """The integration is configurable entirely through the UI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    fields = {
        marker.schema: validator for marker, validator in result["data_schema"].schema.items()
    }
    assert isinstance(fields[CONF_TOKEN], TextSelector)
    assert fields[CONF_TOKEN].config["type"] == "password"


async def test_successful_config_flow(hass: HomeAssistant) -> None:
    """A successful whoami validation creates normalized config-entry data."""
    with patch(
        "custom_components.windmill.api.WindmillClient.async_validate",
        new=AsyncMock(return_value=IDENTITY),
    ):
        result = await _start_user_flow(hass, USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "home-assistant"
    assert result["data"] == {
        CONF_BASE_URL: "https://windmill.example",
        CONF_WORKSPACE: "home-assistant",
        CONF_TOKEN: USER_INPUT[CONF_TOKEN],
    }
    assert result["result"].unique_id is None


@pytest.mark.parametrize(
    ("error", "field", "error_key"),
    [
        (WindmillAuthenticationError(), CONF_TOKEN, "invalid_auth"),
        (WindmillAuthorizationError(), CONF_TOKEN, "insufficient_permission"),
        (WindmillWorkspaceError(), CONF_WORKSPACE, "invalid_workspace"),
        (WindmillConnectionError(), "base", "cannot_connect"),
        (WindmillTimeoutError(), "base", "cannot_connect"),
        (WindmillRateLimitError(), "base", "server_error"),
        (WindmillServerError(), "base", "server_error"),
        (WindmillProtocolError(), "base", "unexpected_response"),
        (WindmillRequestError(), "base", "unexpected_response"),
    ],
)
async def test_config_flow_error_mapping(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    field: str,
    error_key: str,
) -> None:
    """Authentication, connection and protocol failures remain user-distinct."""
    with patch(
        "custom_components.windmill.api.WindmillClient.async_validate",
        new=AsyncMock(side_effect=error),
    ):
        result = await _start_user_flow(hass, USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {field: error_key}
    assert USER_INPUT[CONF_TOKEN] not in caplog.text


async def test_invalid_url_fails_before_request(hass: HomeAssistant) -> None:
    """Remote HTTP and credential-bearing URLs are rejected locally."""
    validate = AsyncMock(return_value=IDENTITY)
    with patch("custom_components.windmill.api.WindmillClient.async_validate", new=validate):
        result = await _start_user_flow(
            hass, {**USER_INPUT, CONF_BASE_URL: "http://windmill.example"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASE_URL: "invalid_url"}
    validate.assert_not_awaited()


@pytest.mark.parametrize(
    ("input_update", "expected_errors"),
    [
        ({CONF_WORKSPACE: "\x00"}, {CONF_WORKSPACE: "invalid_workspace"}),
        ({CONF_TOKEN: ""}, {CONF_TOKEN: "invalid_auth"}),
    ],
)
async def test_invalid_local_input_fails_before_request(
    hass: HomeAssistant,
    input_update: dict[str, str],
    expected_errors: dict[str, str],
) -> None:
    """Invalid workspace and empty token input are rejected locally."""
    validate = AsyncMock(return_value=IDENTITY)
    with patch("custom_components.windmill.api.WindmillClient.async_validate", new=validate):
        result = await _start_user_flow(hass, {**USER_INPUT, **input_update})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_errors
    validate.assert_not_awaited()


async def test_duplicate_normalized_instance_workspace_is_rejected(
    hass: HomeAssistant,
) -> None:
    """Duplicate identity compares normalized non-secret entry data."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="home-assistant",
        data={
            CONF_BASE_URL: "https://windmill.example",
            CONF_WORKSPACE: "home-assistant",
            CONF_TOKEN: "different-fake-token",
        },
    )
    existing.add_to_hass(hass)
    validate = AsyncMock(return_value=IDENTITY)

    with patch("custom_components.windmill.api.WindmillClient.async_validate", new=validate):
        result = await _start_user_flow(
            hass,
            {
                **USER_INPUT,
                CONF_BASE_URL: "HTTPS://WINDMILL.EXAMPLE:443/",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    validate.assert_not_awaited()


async def test_duplicate_percent_encoded_deployment_path_is_rejected(
    hass: HomeAssistant,
) -> None:
    """Equivalent encoded deployment paths share one non-secret identity."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="home-assistant",
        data={
            CONF_BASE_URL: "https://windmill.example/root",
            CONF_WORKSPACE: "home-assistant",
            CONF_TOKEN: "different-fake-token",
        },
    )
    existing.add_to_hass(hass)
    validate = AsyncMock(return_value=IDENTITY)

    with patch("custom_components.windmill.api.WindmillClient.async_validate", new=validate):
        result = await _start_user_flow(
            hass,
            {**USER_INPUT, CONF_BASE_URL: "https://windmill.example/%72oot"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    validate.assert_not_awaited()
