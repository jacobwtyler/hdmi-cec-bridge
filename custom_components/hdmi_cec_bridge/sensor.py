"""Sensor platform for the HDMI CEC Bridge integration."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, OPCODE_NAMES
from .coordinator import (
    SIGNAL_CEC_EVENT,
    SIGNAL_STATE_UPDATE,
    CecBridgeCoordinator,
)
from .models import CecFrame

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CEC Bridge sensors."""
    coordinator: CecBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]
    slug = coordinator.slug

    entities: list[SensorEntity] = [
        CecTvPowerSensor(coordinator, entry, slug),
        CecActiveSourceSensor(coordinator, entry, slug),
        CecRelayCountSensor(coordinator, entry, slug),
    ]

    # Per-tap last event sensors
    for device_id, tap in coordinator.taps.items():
        entities.append(
            CecTapLastEventSensor(coordinator, entry, slug, device_id, tap.label)
        )

    async_add_entities(entities)


class CecTvPowerSensor(RestoreEntity, SensorEntity):
    """Sensor tracking TV/display power state from the output bus."""

    _attr_icon = "mdi:television"
    _attr_has_entity_name = True
    _attr_translation_key = "tv_power"

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
        slug: str,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_tv_power"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"sensor.{slug}_tv_power"

    @property
    def native_value(self) -> str:
        """Return the TV power state."""
        return self._coordinator.tv_power

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return {"last_updated": self._coordinator.last_relay_time or None}

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to updates."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state:
            self._coordinator.tv_power = last_state.state

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_STATE_UPDATE}_{self._coordinator.entry_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        """Handle coordinator state update."""
        self.async_write_ha_state()


class CecActiveSourceSensor(RestoreEntity, SensorEntity):
    """Sensor tracking the active source/input."""

    _attr_icon = "mdi:video-input-hdmi"
    _attr_has_entity_name = True
    _attr_translation_key = "active_source"

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
        slug: str,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_active_source"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"sensor.{slug}_active_source"

    @property
    def native_value(self) -> str:
        """Return the active source label."""
        return self._coordinator.active_source_label

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return {
            "physical_address": self._coordinator.active_source_pa,
            "last_updated": self._coordinator.last_relay_time or None,
        }

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to updates."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state and last_state.state != "unknown":
            self._coordinator.active_source_label = last_state.state
            # Try to find matching tap
            for did, tap in self._coordinator.taps.items():
                if tap.label == last_state.state:
                    self._coordinator.active_input_device_id = did
                    break

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_STATE_UPDATE}_{self._coordinator.entry_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        """Handle coordinator state update."""
        self.async_write_ha_state()


class CecRelayCountSensor(SensorEntity):
    """Sensor tracking the total number of relayed CEC frames."""

    _attr_icon = "mdi:counter"
    _attr_has_entity_name = True
    _attr_translation_key = "relay_count"
    _attr_state_class = "total_increasing"

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
        slug: str,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_relay_count"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"sensor.{slug}_relay_count"

    @property
    def native_value(self) -> int:
        """Return the relay count."""
        return self._coordinator.relay_count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return {
            "last_direction": self._coordinator.last_relay_direction,
            "last_opcode": self._coordinator.last_relay_opcode,
            "last_time": self._coordinator.last_relay_time,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_STATE_UPDATE}_{self._coordinator.entry_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        """Handle coordinator state update."""
        self.async_write_ha_state()


class CecTapLastEventSensor(RestoreEntity, SensorEntity):
    """Sensor showing the last CEC event for a specific tap."""

    _attr_icon = "mdi:message-flash"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
        slug: str,
        device_id: str,
        label: str,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._device_id = device_id
        self._label = label
        tap_slug = re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_last_event"
        self._attr_name = f"{label} Last Event"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"sensor.{slug}_{tap_slug}_last_event"

    @property
    def native_value(self) -> str | None:
        """Return human-readable last event."""
        frame = self._coordinator.tap_last_events.get(self._device_id)
        if frame:
            return frame.summary
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return frame details as attributes."""
        frame = self._coordinator.tap_last_events.get(self._device_id)
        if not frame:
            return {}
        return {
            "opcode": frame.opcode,
            "opcode_hex": frame.opcode_hex,
            "opcode_name": frame.opcode_name,
            "source": f"0x{frame.source:02X}",
            "destination": f"0x{frame.destination:02X}",
            "raw": frame.raw,
            "translated": frame.translated,
        }

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to events."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state:
            # We can't fully reconstruct the CecFrame, but the state is preserved
            pass

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_CEC_EVENT}_{self._coordinator.entry_id}_{self._device_id}",
                self._handle_event,
            )
        )

    @callback
    def _handle_event(self, frame: CecFrame) -> None:
        """Handle a new CEC event for this tap."""
        self.async_write_ha_state()
