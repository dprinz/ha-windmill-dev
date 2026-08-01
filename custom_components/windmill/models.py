"""Runtime models for the Windmill Home Assistant adapter."""

from dataclasses import dataclass

from .api import WindmillClient, WindmillIdentity


@dataclass(slots=True)
class WindmillRuntimeData:
    """Typed runtime data owned by one Windmill config entry."""

    client: WindmillClient
    identity: WindmillIdentity
