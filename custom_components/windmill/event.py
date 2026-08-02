"""Windmill run event entity."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WindmillConfigEntry
from .api import JobState
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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Publish every completion the coordinator observed for the first time."""
        for event in self.coordinator.data.new_events:
            self._trigger_event(
                event.state.value,
                {
                    "job_id": event.job_id,
                    "job_kind": event.kind,
                    "path": event.path,
                    "duration_ms": event.duration_ms,
                },
            )
        super()._handle_coordinator_update()
