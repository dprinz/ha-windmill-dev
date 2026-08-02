"""Runtime models for the Windmill Home Assistant adapter."""

from dataclasses import dataclass

from .api import (
    CapabilityMatrix,
    WindmillClient,
    WindmillConnection,
    WindmillIdentity,
    WindmillServerInfo,
)
from .coordinator import (
    StartedJobRegistry,
    WindmillCapabilityCoordinator,
    WindmillHealthCoordinator,
    WindmillRunCoordinator,
    WindmillRunnableCoordinator,
    WindmillUpdateCoordinator,
    WindmillWorkerCoordinator,
)


@dataclass(slots=True)
class WindmillRuntimeData:
    """Typed runtime data owned by one Windmill config entry."""

    client: WindmillClient
    connection: WindmillConnection
    capability_coordinator: WindmillCapabilityCoordinator
    health_coordinator: WindmillHealthCoordinator | None = None
    worker_coordinator: WindmillWorkerCoordinator | None = None
    run_coordinator: WindmillRunCoordinator | None = None
    runnable_coordinator: WindmillRunnableCoordinator | None = None
    started_jobs: StartedJobRegistry | None = None
    update_coordinator: WindmillUpdateCoordinator | None = None

    @property
    def identity(self) -> WindmillIdentity:
        """Return the validated workspace identity."""
        return self.connection.identity

    @property
    def server(self) -> WindmillServerInfo:
        """Return the validated server facts."""
        return self.connection.server

    @property
    def capabilities(self) -> CapabilityMatrix:
        """Return the coordinator's current capability snapshot."""
        if self.capability_coordinator.data is None:
            raise RuntimeError("Windmill capabilities are not initialized")
        return self.capability_coordinator.data
