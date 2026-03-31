"""Select platform for the HDMI CEC Bridge integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
    """Set up CEC Bridge select entities."""
    coordinator: CecBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.input_taps:
        return

    async_add_entities([CecActiveInputSelect(coordinator, entry)])


class CecActiveInputSelect(RestoreEntity, SelectEntity):
    """Select entity for choosing the active CEC input."""

    _attr_icon = "mdi:video-input-hdmi"
    _attr_has_entity_name = True
    _attr_translation_key = "active_input"

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        slug = coordinator.slug
        self._attr_unique_id = f"{entry.entry_id}_active_input"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"select.{slug}_active_input"

        # Build device_id → label mapping for input taps
        self._input_map: dict[str, str] = {
            did: tap.label
            for did, tap in coordinator.taps.items()
            if tap.is_input
        }
        # Reverse mapping: label → device_id
        self._label_to_device: dict[str, str] = {
            label: did for did, label in self._input_map.items()
        }
        self._attr_options = list(self._input_map.values())

    @property
    def current_option(self) -> str | None:
        """Return the currently active input label."""
        label = self._coordinator.active_source_label
        if label in self._attr_options:
            return label
        return self._attr_options[0] if self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        """Handle the user selecting a new active input."""
        device_id = self._label_to_device.get(option)
        if not device_id:
            return

        tap = self._coordinator.taps.get(device_id)
        if tap:
            await self._coordinator.async_send_active_source(tap)

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to updates."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self._attr_options:
            device_id = self._label_to_device.get(last_state.state)
            if device_id:
                self._coordinator.set_active_input(device_id)

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
