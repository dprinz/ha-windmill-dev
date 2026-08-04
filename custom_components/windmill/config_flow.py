"""Guided configuration and lifecycle flows for the Windmill integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    AddressingMode,
    CapabilityAvailability,
    CapabilityMatrix,
    CapabilityStatus,
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillClient,
    WindmillConnection,
    WindmillConnectionError,
    WindmillError,
    WindmillInstanceClient,
    WindmillNotFoundError,
    WindmillProtocolError,
    WindmillRateLimitError,
    WindmillRequestError,
    WindmillRunnable,
    WindmillServerError,
    WindmillUrlError,
    WindmillWorkspaceError,
    WindmillWorkspaceInfo,
)
from .const import (
    CONF_BASE_URL,
    CONF_TOKEN,
    CONF_WORKSPACE,
    DEFAULT_RUN_SCOPE,
    DOMAIN,
    FEATURE_DEFAULTS,
    FEATURE_OPTIONS,
    MAX_SELECTED_RUNNABLES,
    OPT_DETAILED_HEALTH,
    OPT_INSTANCE_HEALTH,
    OPT_RUN_OBSERVATION,
    OPT_RUN_SCOPE,
    OPT_RUNNABLE_DETAILS,
    OPT_RUNNABLES,
    OPT_UPDATE_ENTITY,
    OPT_WORKER_DETAILS,
    RUN_SCOPES,
)
from .coordinator import (
    RunnableSelection,
    async_discover_runnables,
    load_selections,
    run_scope_from_options,
)

TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
CONF_PIN = "pin_selected"
SELECTION_SEPARATOR = ":"


def _selection_value(kind: str, path: str) -> str:
    """Return the stable form value of one runnable selection."""
    return f"{kind}{SELECTION_SEPARATOR}{path}"


def _selection_label(kind: str, path: str, summary: str) -> str:
    """Return a readable label without exposing anything beyond discovery metadata."""
    return f"{kind}: {path} - {summary}" if summary else f"{kind}: {path}"


def _merge_selections(
    selected: list[str], stored: tuple[RunnableSelection, ...], pin: bool
) -> list[dict[str, str]]:
    """Keep the addressing mode of known runnables and apply the pin choice to new ones."""
    known = {selection.key: selection for selection in stored}
    merged: list[dict[str, str]] = []
    for value in selected:
        kind, separator, path = value.partition(SELECTION_SEPARATOR)
        if not separator:
            continue
        existing = known.get((kind, path))
        if existing is not None:
            merged.append(existing.as_dict())
            continue
        selection = RunnableSelection.from_dict(
            {
                "kind": kind,
                "path": path,
                "mode": AddressingMode.PINNED.value if pin else AddressingMode.LATEST.value,
            }
        )
        if selection is not None:
            merged.append(selection.as_dict())
    return merged


def _map_client_error(err: WindmillError) -> tuple[str, str]:
    """Translate one typed client failure into a field-specific form error."""
    if isinstance(err, WindmillUrlError):
        return (CONF_BASE_URL, "invalid_url")
    if isinstance(err, WindmillAuthenticationError):
        return (CONF_TOKEN, "invalid_auth")
    if isinstance(err, WindmillAuthorizationError):
        return (CONF_TOKEN, "insufficient_permission")
    if isinstance(err, WindmillWorkspaceError):
        return (CONF_WORKSPACE, "invalid_workspace")
    if isinstance(err, WindmillConnectionError):
        return ("base", "cannot_connect")
    if isinstance(err, WindmillRateLimitError | WindmillServerError):
        return ("base", "server_error")
    return ("base", "unexpected_response")


def _feature_capabilities(capabilities: CapabilityMatrix) -> dict[str, CapabilityAvailability]:
    """Map every selectable feature to the capability that has to support it."""
    return {
        OPT_INSTANCE_HEALTH: capabilities.health,
        OPT_DETAILED_HEALTH: capabilities.detailed_health,
        OPT_WORKER_DETAILS: capabilities.workers,
        OPT_RUN_OBSERVATION: capabilities.runs,
        OPT_RUNNABLE_DETAILS: capabilities.runs,
        OPT_UPDATE_ENTITY: capabilities.update_visibility,
    }


def _feature_defaults(capabilities: CapabilityMatrix) -> dict[str, bool]:
    """Enable a feature by default only when it is safe and currently supported.

    Not every feature has a single gating capability — a runnable button needs script *or* flow
    execution — so an unmapped feature keeps its default instead of being suppressed. Writing
    that out explicitly matters: the previous form indexed the map directly and survived only
    because `and` short-circuits on a false default, which would turn the first default flipped
    to true into a `KeyError`.
    """
    supported = _feature_capabilities(capabilities)
    return {
        key: FEATURE_DEFAULTS[key]
        and (key not in supported or supported[key].status is CapabilityStatus.AVAILABLE)
        for key in FEATURE_OPTIONS
    }


def _feature_schema(defaults: Mapping[str, bool], run_scope: str) -> vol.Schema:
    """Build the opt-in feature schema shared by onboarding and options."""
    return vol.Schema(
        {
            vol.Required(key, default=defaults.get(key, FEATURE_DEFAULTS[key])): BooleanSelector()
            for key in FEATURE_OPTIONS
        }
        | {
            vol.Required(OPT_RUN_SCOPE, default=run_scope): SelectSelector(
                SelectSelectorConfig(
                    options=list(RUN_SCOPES),
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=OPT_RUN_SCOPE,
                )
            )
        }
    )


def _selected_features(user_input: Mapping[str, Any]) -> dict[str, bool]:
    """Normalize submitted toggles into a complete boolean feature selection."""
    return {key: bool(user_input.get(key, False)) for key in FEATURE_OPTIONS}


def _feature_options(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a submitted features form into the stored option set."""
    return {
        **_selected_features(user_input),
        OPT_RUN_SCOPE: run_scope_from_options(user_input),
    }


class WindmillConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Guide connection, workspace, capability review and feature selection."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the assistant state shared by the onboarding steps."""
        self._base_url: str = ""
        self._token: str = ""
        self._workspace: str = ""
        self._workspaces: tuple[WindmillWorkspaceInfo, ...] | None = None
        self._connection: WindmillConnection | None = None
        self._capabilities: CapabilityMatrix | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WindmillOptionsFlow:
        """Return the feature options flow for an existing entry."""
        return WindmillOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Validate the instance and credential before anything else is offered."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_instance(
                user_input[CONF_BASE_URL], user_input[CONF_TOKEN]
            )
            if not errors:
                return await self.async_step_workspace()

        default_base_url = user_input.get(CONF_BASE_URL, "https://") if user_input else "https://"
        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default=default_base_url): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Required(CONF_TOKEN): TOKEN_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"cloud_url": "https://app.windmill.dev"},
            last_step=False,
        )

    async def async_step_workspace(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the workspace and validate access to it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = WindmillClient(
                    async_get_clientsession(self.hass),
                    self._base_url,
                    user_input[CONF_WORKSPACE],
                    self._token,
                )
            except WindmillError as err:
                field, error = _map_client_error(err)
                errors[field] = error
            else:
                if self._async_find_entry(client.base_url, client.workspace) is not None:
                    return self.async_abort(reason="already_configured")
                try:
                    connection = await client.async_connect()
                    capabilities = await client.async_discover_capabilities()
                except WindmillError as err:
                    field, error = _map_client_error(err)
                    errors[field] = error
                else:
                    self._workspace = client.workspace
                    self._connection = connection
                    self._capabilities = capabilities
                    return await self.async_step_capabilities()

        return self.async_show_form(
            step_id="workspace",
            data_schema=self._workspace_schema(user_input),
            errors=errors,
            last_step=False,
        )

    async def async_step_capabilities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Explain what the validated token can and cannot do."""
        if user_input is not None:
            return await self.async_step_features()
        return self.async_show_form(
            step_id="capabilities",
            data_schema=vol.Schema({}),
            description_placeholders=self._capability_placeholders(),
            last_step=False,
        )

    async def async_step_features(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user opt into the features their permissions support."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._workspace,
                data={
                    CONF_BASE_URL: self._base_url,
                    CONF_WORKSPACE: self._workspace,
                    CONF_TOKEN: self._token,
                },
                options=_feature_options(user_input),
            )

        capabilities = self._require_capabilities()
        return self.async_show_form(
            step_id="features",
            data_schema=_feature_schema(_feature_defaults(capabilities), DEFAULT_RUN_SCOPE),
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start credential replacement for an existing entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Replace only the credential of an entry with immutable identity."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_workspace_access(
                entry.data[CONF_BASE_URL],
                entry.data[CONF_WORKSPACE],
                user_input[CONF_TOKEN],
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): TOKEN_SELECTOR}),
            errors=errors,
            description_placeholders={
                CONF_BASE_URL: entry.data[CONF_BASE_URL],
                CONF_WORKSPACE: entry.data[CONF_WORKSPACE],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change connection identity without deleting the entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input.get(CONF_TOKEN) or entry.data[CONF_TOKEN]
            try:
                client = WindmillClient(
                    async_get_clientsession(self.hass),
                    user_input[CONF_BASE_URL],
                    user_input[CONF_WORKSPACE],
                    token,
                )
            except WindmillError as err:
                field, error = _map_client_error(err)
                errors[field] = error
            else:
                if (
                    self._async_find_entry(
                        client.base_url, client.workspace, ignore_entry_id=entry.entry_id
                    )
                    is not None
                ):
                    return self.async_abort(reason="already_configured")
                try:
                    await client.async_connect()
                except WindmillError as err:
                    field, error = _map_client_error(err)
                    errors[field] = error
                else:
                    # The entry title is user-owned; reconfiguration only changes identity.
                    return self.async_update_reload_and_abort(
                        entry,
                        data={
                            CONF_BASE_URL: client.base_url,
                            CONF_WORKSPACE: client.workspace,
                            CONF_TOKEN: token,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BASE_URL,
                    default=entry.data[CONF_BASE_URL],
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                vol.Required(
                    CONF_WORKSPACE,
                    default=entry.data[CONF_WORKSPACE],
                ): str,
                vol.Optional(CONF_TOKEN): TOKEN_SELECTOR,
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    async def _async_validate_instance(self, base_url: str, token: str) -> dict[str, str]:
        """Validate reachability and the credential before workspace selection."""
        try:
            client = WindmillInstanceClient(async_get_clientsession(self.hass), base_url, token)
        except WindmillError as err:
            field, error = _map_client_error(err)
            return {field: error}

        try:
            await client.async_get_server_info()
        except WindmillError as err:
            field, error = _map_client_error(err)
            return {field: error}

        workspaces: tuple[WindmillWorkspaceInfo, ...] | None = None
        try:
            workspaces = await client.async_list_workspaces()
        except WindmillAuthenticationError as err:
            field, error = _map_client_error(err)
            return {field: error}
        except (
            WindmillAuthorizationError,
            WindmillNotFoundError,
            WindmillProtocolError,
            WindmillRequestError,
        ):
            # A restricted token may not list workspaces; fall back to manual entry.
            workspaces = None
        except WindmillError as err:
            field, error = _map_client_error(err)
            return {field: error}

        self._base_url = client.base_url
        self._token = token
        self._workspaces = workspaces
        return {}

    async def _async_validate_workspace_access(
        self, base_url: str, workspace: str, token: str
    ) -> dict[str, str]:
        """Validate that a credential still grants access to a stored identity."""
        try:
            client = WindmillClient(async_get_clientsession(self.hass), base_url, workspace, token)
            await client.async_connect()
        except WindmillError as err:
            field, error = _map_client_error(err)
            return {field: error}
        return {}

    @callback
    def _async_find_entry(
        self, base_url: str, workspace: str, *, ignore_entry_id: str | None = None
    ) -> ConfigEntry | None:
        """Return an existing entry with the same canonical non-secret identity."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.entry_id == ignore_entry_id:
                continue
            if (
                entry.data.get(CONF_BASE_URL) == base_url
                and entry.data.get(CONF_WORKSPACE) == workspace
            ):
                return entry
        return None

    def _workspace_schema(self, user_input: Mapping[str, Any] | None) -> vol.Schema:
        """Offer discovered workspaces when listing them was authorized."""
        default = user_input.get(CONF_WORKSPACE, "") if user_input else ""
        if not self._workspaces:
            return vol.Schema({vol.Required(CONF_WORKSPACE, default=default): str})

        options = [
            SelectOptionDict(value=workspace.id, label=f"{workspace.name} ({workspace.id})")
            for workspace in self._workspaces
        ]
        selector = SelectSelector(
            SelectSelectorConfig(
                options=options,
                mode=SelectSelectorMode.DROPDOWN,
                custom_value=True,
                sort=True,
            )
        )
        if default:
            return vol.Schema({vol.Required(CONF_WORKSPACE, default=default): selector})
        return vol.Schema({vol.Required(CONF_WORKSPACE): selector})

    def _capability_placeholders(self) -> dict[str, str]:
        """Describe the detected capabilities without exposing any credential."""
        capabilities = self._require_capabilities()
        connection = self._connection
        if connection is None:  # pragma: no cover - guarded by the step order
            raise RuntimeError("Windmill connection facts are missing")
        return {
            "server": f"{connection.server.edition.upper()} {connection.server.version}",
            "username": connection.identity.username,
            "workspace": self._workspace,
            "health": capabilities.health.status.value,
            "detailed_health": capabilities.detailed_health.status.value,
            "workers": capabilities.workers.status.value,
            "runs": capabilities.runs.status.value,
            "script_discovery": capabilities.script_discovery.status.value,
            "flow_discovery": capabilities.flow_discovery.status.value,
            "update_visibility": capabilities.update_visibility.status.value,
        }

    def _require_capabilities(self) -> CapabilityMatrix:
        """Return the discovered capability matrix of the current assistant run."""
        if self._capabilities is None:  # pragma: no cover - guarded by the step order
            raise RuntimeError("Windmill capabilities are missing")
        return self._capabilities


class WindmillOptionsFlow(OptionsFlowWithReload):
    """Adjust opt-in features and runnable selection without touching identity."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Offer the two independent option areas."""
        return self.async_show_menu(step_id="init", menu_options=["features", "runnables"])

    async def async_step_features(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the feature selection of an existing entry."""
        if user_input is not None:
            return self._async_save(_feature_options(user_input))

        current = {
            key: bool(self.config_entry.options.get(key, FEATURE_DEFAULTS[key]))
            for key in FEATURE_OPTIONS
        }
        return self.async_show_form(
            step_id="features",
            data_schema=_feature_schema(current, run_scope_from_options(self.config_entry.options)),
        )

    async def async_step_runnables(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose exactly which scripts and flows are exposed."""
        stored = load_selections(self.config_entry.options.get(OPT_RUNNABLES))
        if user_input is not None:
            selected = user_input.get(OPT_RUNNABLES, [])
            if len(selected) > MAX_SELECTED_RUNNABLES:
                return self.async_show_form(
                    step_id="runnables",
                    data_schema=self._runnable_schema(await self._async_discover(), stored),
                    errors={OPT_RUNNABLES: "too_many_runnables"},
                )
            return self._async_save(
                {OPT_RUNNABLES: _merge_selections(selected, stored, bool(user_input.get(CONF_PIN)))}
            )

        return self.async_show_form(
            step_id="runnables",
            data_schema=self._runnable_schema(await self._async_discover(), stored),
        )

    async def _async_discover(self) -> tuple[WindmillRunnable, ...]:
        """Discover selectable runnables through the entry's runtime client."""
        runtime = getattr(self.config_entry, "runtime_data", None)
        if runtime is None:
            return ()
        return await async_discover_runnables(runtime.client)

    def _runnable_schema(
        self, discovered: tuple[WindmillRunnable, ...], stored: tuple[RunnableSelection, ...]
    ) -> vol.Schema:
        """Build a bounded multi-select that keeps unavailable selections visible."""
        options = {
            _selection_value(runnable.kind.value, runnable.path): _selection_label(
                runnable.kind.value, runnable.path, runnable.summary
            )
            for runnable in discovered
        }
        for selection in stored:
            value = _selection_value(selection.kind.value, selection.path)
            options.setdefault(value, _selection_label(selection.kind.value, selection.path, ""))
        return vol.Schema(
            {
                vol.Optional(
                    OPT_RUNNABLES,
                    default=[
                        _selection_value(selection.kind.value, selection.path)
                        for selection in stored
                    ],
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=value, label=label)
                            for value, label in sorted(options.items())
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        sort=True,
                    )
                ),
                vol.Optional(CONF_PIN, default=False): BooleanSelector(),
            }
        )

    @callback
    def _async_save(self, updates: dict[str, Any]) -> ConfigFlowResult:
        """Store one option area without discarding the other."""
        return self.async_create_entry(data={**self.config_entry.options, **updates})
