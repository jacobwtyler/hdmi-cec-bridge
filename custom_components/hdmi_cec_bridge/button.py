"""Button platform for the HDMI CEC Bridge integration."""

from __future__ import annotations

import logging
import re

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CEC_ADDR_BROADCAST,
    CEC_ADDR_TV,
    CEC_OPCODE_ACTIVE_SOURCE,
    CEC_OPCODE_GIVE_POWER_STATUS,
    CEC_OPCODE_IMAGE_VIEW_ON,
    CEC_OPCODE_STANDBY,
    DOMAIN,
)
from .coordinator import CecBridgeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CEC Bridge buttons."""
    coordinator: CecBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]
    slug = coordinator.slug
    output = coordinator.primary_output

    if not output:
        return

    entities: list[ButtonEntity] = [
        CecWakeTvButton(coordinator, entry, slug),
        CecStandbyAllButton(coordinator, entry, slug),
        CecRequestTvPowerButton(coordinator, entry, slug),
        CecRequestAllPowerButton(coordinator, entry, slug),
        CecRequestAudioStatusButton(coordinator, entry, slug),
    ]

    # Per-input "Switch to" buttons
    for device_id, tap in coordinator.taps.items():
        if tap.is_input and tap.pa_bytes:
            entities.append(
                CecSwitchToInputButton(coordinator, entry, slug, device_id, tap.label)
            )

    async_add_entities(entities)


class CecWakeTvButton(ButtonEntity):
    """Button to send Image View On to the TV."""

    _attr_icon = "mdi:television"
    _attr_has_entity_name = True
    _attr_translation_key = "wake_tv"

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
        slug: str,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_wake_tv"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"button.{slug}_wake_tv"

    async def async_press(self) -> None:
        """Send Image View On to TV via output tap."""
        output = self._coordinator.primary_output
        if output:
            await self._coordinator.async_send_cec(
                output, CEC_ADDR_TV, [CEC_OPCODE_IMAGE_VIEW_ON]
            )


class CecStandbyAllButton(ButtonEntity):
    """Button to send Standby broadcast."""

    _attr_icon = "mdi:power-sleep"
    _attr_has_entity_name = True
    _attr_translation_key = "standby_all"

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
        slug: str,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_standby_all"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"button.{slug}_standby_all"

    async def async_press(self) -> None:
        """Send Standby broadcast via output tap."""
        output = self._coordinator.primary_output
        if output:
            await self._coordinator.async_send_cec(
                output, CEC_ADDR_BROADCAST, [CEC_OPCODE_STANDBY]
            )


class CecRequestTvPowerButton(ButtonEntity):
    """Button to request TV power status."""

    _attr_icon = "mdi:help-circle-outline"
    _attr_has_entity_name = True
    _attr_translation_key = "request_tv_power"

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
        slug: str,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_request_tv_power"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"button.{slug}_request_tv_power"

    async def async_press(self) -> None:
        """Send Give Power Status to TV via output tap."""
        output = self._coordinator.primary_output
        if output:
            await self._coordinator.async_send_cec(
                output, CEC_ADDR_TV, [CEC_OPCODE_GIVE_POWER_STATUS]
            )


class CecRequestAllPowerButton(ButtonEntity):
    """Button to request power status from all devices."""

    _attr_icon = "mdi:help-circle"
    _attr_has_entity_name = True
    _attr_translation_key = "request_all_power"

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
        slug: str,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_request_all_power"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"button.{slug}_request_all_power"

    async def async_press(self) -> None:
        """Send Give Power Status broadcast via output tap."""
        output = self._coordinator.primary_output
        if output:
            await self._coordinator.async_send_cec(
                output, CEC_ADDR_BROADCAST, [CEC_OPCODE_GIVE_POWER_STATUS]
            )


class CecRequestAudioStatusButton(ButtonEntity):
    """Button to request audio status from the audio system."""

    _attr_icon = "mdi:volume-high"
    _attr_has_entity_name = True
    _attr_translation_key = "request_audio_status"

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
        slug: str,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_request_audio_status"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"button.{slug}_request_audio_status"

    async def async_press(self) -> None:
        """Send Give Audio Status to audio system via output tap."""
        await self._coordinator.async_request_audio_status()


class CecSwitchToInputButton(ButtonEntity):
    """Button to switch to a specific input by sending Active Source."""

    _attr_icon = "mdi:video-input-hdmi"
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
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_switch_to"
        self._attr_name = f"Switch to {label}"
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"button.{slug}_switch_to_{tap_slug}"

    async def async_press(self) -> None:
        """Send Active Source for this input via output tap."""
        tap = self._coordinator.taps.get(self._device_id)
        if tap:
            await self._coordinator.async_send_active_source(tap)
