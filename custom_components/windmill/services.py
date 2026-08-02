"""Home Assistant actions that start explicitly selected Windmill runnables."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import (
    AddressingMode,
    RunnableKind,
    RunnableParameter,
    WindmillAuthenticationError,
    WindmillAuthorizationError,
    WindmillConnectionError,
    WindmillError,
    WindmillNotFoundError,
    WindmillRateLimitError,
    WindmillServerError,
)
from .const import ATTR_ARGUMENTS, ATTR_CONFIG_ENTRY_ID, ATTR_KIND, ATTR_PATH, DOMAIN
from .coordinator import ResolvedRunnable
from .models import WindmillRuntimeData

type WindmillEntry = ConfigEntry[WindmillRuntimeData]

SERVICE_RUN = "run"
MAX_ARGUMENT_BYTES = 8_192

RUN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_KIND): vol.In([kind.value for kind in RunnableKind]),
        vol.Required(ATTR_PATH): cv.string,
        vol.Optional(ATTR_ARGUMENTS, default=dict): vol.Schema({str: object}),
    }
)

_ERROR_KEYS = {
    WindmillAuthenticationError: "invalid_auth",
    WindmillAuthorizationError: "insufficient_permission",
    WindmillNotFoundError: "runnable_missing",
    WindmillConnectionError: "cannot_connect",
    WindmillRateLimitError: "server_error",
    WindmillServerError: "server_error",
}


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register the Windmill actions once for the whole integration."""
    if hass.services.has_service(DOMAIN, SERVICE_RUN):
        return

    async def async_run(call: ServiceCall) -> ServiceResponse:
        """Start one selected runnable and return bounded metadata."""
        entry = _async_resolve_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        kind = RunnableKind(call.data[ATTR_KIND])
        path = call.data[ATTR_PATH]
        resolved = _async_resolve_runnable(entry, kind, path)
        arguments = validate_arguments(resolved, call.data[ATTR_ARGUMENTS])
        job_id = await async_start_runnable(entry, resolved, arguments)
        return {"job_id": job_id}

    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN,
        async_run,
        schema=RUN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_start_runnable(
    entry: WindmillEntry, resolved: ResolvedRunnable, arguments: Mapping[str, Any]
) -> str:
    """Start one resolved runnable and translate client failures for the caller."""
    details = resolved.details
    pinned = resolved.selection.mode is AddressingMode.PINNED
    if pinned and (
        details is None or (details.script_hash is None and details.flow_version is None)
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="pin_unavailable",
            translation_placeholders={"path": resolved.selection.path},
        )
    try:
        return await entry.runtime_data.client.async_run_runnable(
            resolved.selection.kind,
            resolved.selection.path,
            arguments,
            script_hash=details.script_hash if pinned and details is not None else None,
            flow_version=details.flow_version if pinned and details is not None else None,
        )
    except WindmillError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=_error_key(err),
            translation_placeholders={"path": resolved.selection.path},
        ) from err


def validate_arguments(resolved: ResolvedRunnable, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Validate arguments against the bounded schema projection before any request."""
    if not isinstance(arguments, Mapping):  # pragma: no cover - guarded by the action schema
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_arguments")
    details = resolved.details
    payload = dict(arguments)
    try:
        encoded = json.dumps(payload)
    except (TypeError, ValueError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_arguments"
        ) from err
    if len(encoded.encode("utf-8")) > MAX_ARGUMENT_BYTES:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="arguments_too_large"
        )
    if details is None:  # pragma: no cover - unavailable runnables are rejected earlier
        return payload

    known = {parameter.name: parameter for parameter in details.parameters}
    unknown = sorted(set(payload) - set(known))
    if unknown:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_arguments",
            translation_placeholders={"names": ", ".join(unknown)},
        )
    missing = sorted(
        name for name, parameter in known.items() if parameter.required and name not in payload
    )
    if missing:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_arguments",
            translation_placeholders={"names": ", ".join(missing)},
        )
    for name, value in payload.items():
        _validate_value(known[name], value)
    return payload


def _validate_value(parameter: RunnableParameter, value: Any) -> None:
    """Check one argument against its declared type and bounded enum."""
    types: dict[str, tuple[type, ...]] = {
        "string": (str,),
        "number": (int, float),
        "integer": (int,),
        "boolean": (bool,),
        "array": (list,),
        "object": (dict,),
    }
    expected = types.get(parameter.type)
    valid = value is None or expected is None or isinstance(value, expected)
    if parameter.type in {"number", "integer"} and isinstance(value, bool):
        valid = False
    if not valid:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_argument_type",
            translation_placeholders={"name": parameter.name, "type": parameter.type},
        )
    if parameter.enum is not None and value is not None and value not in parameter.enum:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_argument_value",
            translation_placeholders={"name": parameter.name},
        )


@callback
def _async_resolve_entry(hass: HomeAssistant, entry_id: str) -> WindmillEntry:
    """Return one loaded Windmill config entry."""
    entry: WindmillEntry | None = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="unknown_config_entry"
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_loaded")
    return entry


@callback
def _async_resolve_runnable(
    entry: WindmillEntry, kind: RunnableKind, path: str
) -> ResolvedRunnable:
    """Return one selected, available runnable with a supported argument schema."""
    coordinator = entry.runtime_data.runnable_coordinator
    resolved: ResolvedRunnable | None = (
        None if coordinator is None else coordinator.data.get((kind.value, path))
    )
    if resolved is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="runnable_not_selected",
            translation_placeholders={"path": path},
        )
    if not resolved.available:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="runnable_unavailable",
            translation_placeholders={"path": path},
        )
    if not resolved.executable:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="runnable_unsupported",
            translation_placeholders={"path": path},
        )
    return resolved


def _error_key(err: WindmillError) -> str:
    """Map one client failure to a stable user-facing error key."""
    for error_type, key in _ERROR_KEYS.items():
        if isinstance(err, error_type):
            return key
    return "unexpected_response"
