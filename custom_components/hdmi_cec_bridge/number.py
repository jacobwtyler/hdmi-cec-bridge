"""Number platform for the HDMI CEC Bridge integration — volume slider."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import SIGNAL_STATE_UPDATE, CecBridgeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CEC Bridge number entities."""
    coordinator: CecBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.primary_output:
        return

    async_add_entities([CecVolumeNumber(coordinator, entry)])


class CecVolumeNumber(RestoreEntity, NumberEntity):
    """Number entity for CEC audio volume (0-100 slider)."""

    _attr_icon = "mdi:volume-high"
    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        slug = coordinator.slug
        self._attr_unique_id = f"{entry.entry_id}_audio_volume"
        self._attr_name = "Audio Volume"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"number.{slug}_audio_volume"

    @property
    def native_value(self) -> float | None:
        """Return the current volume."""
        return self._coordinator.audio_volume

    @property
    def extra_state_attributes(self) -> dict:
        """Return mute state as an attribute."""
        return {"muted": self._coordinator.audio_muted}

    async def async_set_native_value(self, value: float) -> None:
        """Set volume to the target value."""
        await self._coordinator.async_set_volume(int(value))

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to updates."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._coordinator.audio_volume = int(float(last_state.state))
            except (ValueError, TypeError):
                pass
            self._coordinator.audio_muted = (
                last_state.attributes.get("muted", False)
            )

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
