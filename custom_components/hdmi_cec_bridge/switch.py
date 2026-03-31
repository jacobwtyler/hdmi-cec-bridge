"""Switch platform for the HDMI CEC Bridge integration — relay rule toggles."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_RELAY_RULES, DOMAIN, RELAY_RULE_DESCRIPTIONS
from .coordinator import CecBridgeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CEC Bridge relay rule switches."""
    coordinator: CecBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]
    slug = coordinator.slug

    entities = [
        CecRelayRuleSwitch(coordinator, entry, slug, rule_key, default_on)
        for rule_key, default_on in DEFAULT_RELAY_RULES.items()
    ]

    async_add_entities(entities)


class CecRelayRuleSwitch(RestoreEntity, SwitchEntity):
    """Switch to enable/disable a CEC relay rule."""

    _attr_icon = "mdi:swap-horizontal"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CecBridgeCoordinator,
        entry: ConfigEntry,
        slug: str,
        rule_key: str,
        default_on: bool,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._rule_key = rule_key
        self._default_on = default_on
        self._attr_unique_id = f"{entry.entry_id}_{rule_key}"
        self._attr_name = RELAY_RULE_DESCRIPTIONS.get(rule_key, rule_key)
        self._attr_device_info = coordinator.device_info
        self.entity_id = f"switch.{slug}_{rule_key}"

    @property
    def is_on(self) -> bool:
        """Return whether the relay rule is enabled."""
        return self._coordinator.relay_rules.get(self._rule_key, self._default_on)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the relay rule."""
        self._coordinator.relay_rules[self._rule_key] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the relay rule."""
        self._coordinator.relay_rules[self._rule_key] = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore previous state."""
        last_state = await self.async_get_last_state()
        if last_state:
            self._coordinator.relay_rules[self._rule_key] = (
                last_state.state == "on"
            )
        else:
            self._coordinator.relay_rules[self._rule_key] = self._default_on
