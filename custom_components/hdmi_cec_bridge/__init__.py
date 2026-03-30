"""The HDMI CEC Bridge integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_BRIDGE_NAME, CONF_TAPS, DOMAIN
from .coordinator import CecBridgeCoordinator
from .models import CecTap

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HDMI CEC Bridge from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    bridge_name = entry.data.get(CONF_BRIDGE_NAME, "CEC Bridge")
    taps_config = entry.data.get(CONF_TAPS, {})

    # Build CecTap objects
    taps = {
        device_id: CecTap.from_config(device_id, config)
        for device_id, config in taps_config.items()
    }

    # Create coordinator
    coordinator = CecBridgeCoordinator(hass, entry.entry_id, bridge_name, taps)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Start event listeners
    await coordinator.async_start()

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info(
        "HDMI CEC Bridge '%s' set up with %d taps", bridge_name, len(taps)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: CecBridgeCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        await coordinator.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update — reload the entry."""
    if entry.options.get(CONF_TAPS):
        # Merge options tap changes back into data
        new_data = dict(entry.data)
        new_data[CONF_TAPS] = entry.options[CONF_TAPS]
        hass.config_entries.async_update_entry(entry, data=new_data, options={})
    await hass.config_entries.async_reload(entry.entry_id)
