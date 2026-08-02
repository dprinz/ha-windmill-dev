"""Windmill run event entity."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.start import async_at_started

from . import WindmillConfigEntry
from .api import JobState
from .coordinator import WindmillRunSnapshot
from .entity import WindmillRunEntity

RUN_EVENT_TYPES = [JobState.SUCCESS.value, JobState.FAILURE.value, JobState.CANCELED.value]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WindmillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the single run event entity when run observation is enabled."""
    runtime = entry.runtime_data
    coordinator = runtime.run_coordinator
    if coordinator is None:
        return
    async_add_entities([WindmillRunEventEntity(coordinator, entry.entry_id, entry.title, runtime)])


class WindmillRunEventEntity(WindmillRunEntity, EventEntity):
    """Publish one bounded event per newly observed job completion."""

    _key = "run"
    _attr_event_types = RUN_EVENT_TYPES
    _published: WindmillRunSnapshot | None = None

    async def async_added_to_hass(self) -> None:
        """Deliver the completions the refresh during setup observed before this entity existed."""
        await super().async_added_to_hass()
        # The refresh during config-entry setup runs before this entity exists, so its snapshot
        # never arrives through a listener notification. Automations attach their triggers only
        # once Home Assistant has started, so the catch-up delivery waits for that moment; on a
        # reload Home Assistant is already running and it fires immediately.
        self.async_on_remove(async_at_started(self.hass, self._async_deliver_pending))

    @callback
    def _async_deliver_pending(self, hass: HomeAssistant) -> None:
        """Route the pending snapshot through the same guard as any listener notification."""
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Publish every completion the coordinator observed for the first time."""
        snapshot = self.coordinator.data
        if not self.coordinator.last_update_success or snapshot is self._published:
            # A failed poll still notifies listeners while `coordinator.data` holds the previous
            # snapshot. Publishing it again would fire every automation a second time for
            # completions that happened once, so only a fresh observation may publish.
            super()._handle_coordinator_update()
            return
        self._published = snapshot
        registry = self.runtime.started_jobs
        completed: list[str] = []
        for event in snapshot.new_events:
            tracked = None if registry is None else registry.get(event.job_id)
            self._trigger_event(
                event.state.value,
                {
                    "job_id": event.job_id,
                    "job_kind": event.kind,
                    "path": event.path,
                    "duration_ms": event.duration_ms,
                    "started_by_home_assistant": tracked is not None,
                },
            )
            # A triggered event only becomes observable through a state write, so a poll that
            # observes several completions needs one write per completion.
            self.async_write_ha_state()
            if tracked is not None:
                completed.append(event.job_id)
        entry = self.coordinator.config_entry
        if completed and registry is not None and entry is not None:
            # One entry-owned task per poll: an unload waits for it, and the registry writes
            # of one poll cannot interleave with each other.
            entry.async_create_task(
                self.hass,
                registry.async_forget(*completed),
                name="forget completed jobs",
            )
        super()._handle_coordinator_update()
