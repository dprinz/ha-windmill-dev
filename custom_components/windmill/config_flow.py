"""Config flow for the Windmill integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import (
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillClient,
    WindmillConnectionError,
    WindmillProtocolError,
    WindmillRateLimitError,
    WindmillRequestError,
    WindmillServerError,
    WindmillUrlError,
    WindmillWorkspaceError,
    normalize_base_url,
    normalize_workspace,
)
from .const import CONF_BASE_URL, CONF_TOKEN, CONF_WORKSPACE, DOMAIN


class WindmillConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle user configuration of a Windmill instance and workspace."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Validate user input and create a config entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                base_url = normalize_base_url(user_input[CONF_BASE_URL])
                workspace = normalize_workspace(user_input[CONF_WORKSPACE])
                token = user_input[CONF_TOKEN]
                client = WindmillClient(
                    async_get_clientsession(self.hass),
                    base_url,
                    workspace,
                    token,
                )
            except WindmillUrlError:
                errors[CONF_BASE_URL] = "invalid_url"
            except WindmillWorkspaceError:
                errors[CONF_WORKSPACE] = "invalid_workspace"
            except WindmillAuthenticationError:
                errors[CONF_TOKEN] = "invalid_auth"
            else:
                if any(
                    entry.data.get(CONF_BASE_URL) == base_url
                    and entry.data.get(CONF_WORKSPACE) == workspace
                    for entry in self._async_current_entries()
                ):
                    return self.async_abort(reason="already_configured")

                try:
                    await client.async_validate()
                except WindmillAuthenticationError:
                    errors[CONF_TOKEN] = "invalid_auth"
                except WindmillAuthorizationError:
                    errors[CONF_TOKEN] = "insufficient_permission"
                except WindmillWorkspaceError:
                    errors[CONF_WORKSPACE] = "invalid_workspace"
                except WindmillConnectionError:
                    errors["base"] = "cannot_connect"
                except WindmillRateLimitError, WindmillServerError:
                    errors["base"] = "server_error"
                except WindmillProtocolError, WindmillRequestError:
                    errors["base"] = "unexpected_response"
                else:
                    return self.async_create_entry(
                        title=workspace,
                        data={
                            CONF_BASE_URL: base_url,
                            CONF_WORKSPACE: workspace,
                            CONF_TOKEN: token,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BASE_URL,
                    default=user_input.get(CONF_BASE_URL, "https://") if user_input else "https://",
                ): str,
                vol.Required(
                    CONF_WORKSPACE,
                    default=user_input.get(CONF_WORKSPACE, "") if user_input else "",
                ): str,
                vol.Required(CONF_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
