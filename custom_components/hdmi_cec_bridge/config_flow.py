"""Config flow for HDMI CEC Bridge integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    CONF_BRIDGE_NAME,
    CONF_CATCH_ALL_EVENT,
    CONF_DEVICE_ADDRESS,
    CONF_ESPHOME_DEVICE,
    CONF_ESPHOME_SERVICE,
    CONF_PHYSICAL_ADDRESS,
    CONF_TAP_ADDRESS,
    CONF_TAP_LABEL,
    CONF_TAP_ROLE,
    CONF_TAPS,
    DOMAIN,
    ROLE_INPUT,
    ROLE_OUTPUT,
)

_LOGGER = logging.getLogger(__name__)


def _discover_cec_devices(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Discover ESPHome devices with HDMI CEC entities.

    Returns {device_id: {device_name, esphome_device, suggested_event, suggested_service}}.
    """
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    # Find all ESPHome entities that contain "hdmi_cec" or "cec" in their entity_id
    cec_entities = [
        entry
        for entry in entity_reg.entities.values()
        if entry.platform == "esphome"
        and ("hdmi_cec" in entry.entity_id or "cec_raw_message" in entry.entity_id or "cec_translated_message" in entry.entity_id)
    ]

    # Map to unique devices
    device_ids = {e.device_id for e in cec_entities if e.device_id}
    discovered = {}

    for did in device_ids:
        device = device_reg.async_get(did)
        if not device:
            continue

        # Find the ESPHome config entry for this device to get device_name
        esphome_device_name = None
        for config_entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(config_entry_id)
            if entry and entry.domain == "esphome":
                esphome_device_name = entry.data.get("device_name")
                break

        if not esphome_device_name:
            # Fallback: derive from device name
            name = device.name or ""
            esphome_device_name = name.lower().replace(" ", "_").replace("-", "_")

        # The underscored version for service calls (hyphens become underscores)
        service_name = esphome_device_name.replace("-", "_")

        # Suggest catch-all event name based on ESPHome convention
        # e.g., "cec-output-tap" → "esphome.hdmi_cec_output" (matching user's YAML pattern)
        # We can't know for sure, so suggest the common pattern
        suggested_event = f"esphome.hdmi_cec_{service_name.replace('cec_', '').replace('_tap', '')}"

        discovered[did] = {
            "device_name": device.name_by_user or device.name or esphome_device_name,
            "esphome_device": esphome_device_name,
            "esphome_service": f"{service_name}_hdmi_cec_send",
            "suggested_event": suggested_event,
        }

    return discovered


class HdmiCecBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HDMI CEC Bridge."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered: dict[str, dict[str, Any]] = {}
        self._selected_device_ids: list[str] = []
        self._taps_config: dict[str, dict[str, Any]] = {}
        self._current_tap_index: int = 0
        self._bridge_name: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step — discover CEC taps and let user select."""
        self._discovered = _discover_cec_devices(self.hass)

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            self._bridge_name = user_input.get(CONF_BRIDGE_NAME, "CEC Bridge")
            selected = user_input.get("selected_devices", [])
            if not selected:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._build_user_schema(),
                    errors={"base": "no_devices_selected"},
                )
            self._selected_device_ids = selected
            self._current_tap_index = 0
            return await self.async_step_configure_tap()

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_user_schema(),
        )

    def _build_user_schema(self) -> vol.Schema:
        """Build schema for device selection step."""
        device_options = {
            did: info["device_name"] for did, info in self._discovered.items()
        }
        return vol.Schema(
            {
                vol.Required(CONF_BRIDGE_NAME, default="CEC Bridge"): str,
                vol.Required("selected_devices"): vol.All(
                    vol.Coerce(list),
                    [vol.In(device_options)],
                ),
            }
        )

    async def async_step_configure_tap(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure each selected tap one at a time."""
        if user_input is not None:
            device_id = self._selected_device_ids[self._current_tap_index]
            self._taps_config[device_id] = {
                CONF_TAP_LABEL: user_input[CONF_TAP_LABEL],
                CONF_TAP_ROLE: user_input[CONF_TAP_ROLE],
                CONF_ESPHOME_DEVICE: self._discovered[device_id]["esphome_device"],
                CONF_ESPHOME_SERVICE: user_input.get(
                    CONF_ESPHOME_SERVICE,
                    self._discovered[device_id]["esphome_service"],
                ),
                CONF_CATCH_ALL_EVENT: user_input[CONF_CATCH_ALL_EVENT],
                CONF_TAP_ADDRESS: user_input[CONF_TAP_ADDRESS],
                CONF_PHYSICAL_ADDRESS: user_input.get(CONF_PHYSICAL_ADDRESS),
                CONF_DEVICE_ADDRESS: user_input.get(CONF_DEVICE_ADDRESS),
            }
            self._current_tap_index += 1

            if self._current_tap_index < len(self._selected_device_ids):
                return await self.async_step_configure_tap()

            # Validate: need at least one output and one input
            roles = [t[CONF_TAP_ROLE] for t in self._taps_config.values()]
            if ROLE_OUTPUT not in roles:
                return self.async_abort(reason="no_output_tap")
            if ROLE_INPUT not in roles:
                return self.async_abort(reason="no_input_tap")

            # Create the entry
            await self.async_set_unique_id(
                f"cec_bridge_{self._bridge_name.lower().replace(' ', '_')}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._bridge_name,
                data={
                    CONF_BRIDGE_NAME: self._bridge_name,
                    CONF_TAPS: self._taps_config,
                },
            )

        # Show form for current tap
        device_id = self._selected_device_ids[self._current_tap_index]
        info = self._discovered[device_id]
        tap_num = self._current_tap_index + 1
        total = len(self._selected_device_ids)

        return self.async_show_form(
            step_id="configure_tap",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TAP_LABEL, default=info["device_name"]
                    ): str,
                    vol.Required(CONF_TAP_ROLE, default=ROLE_INPUT): vol.In(
                        {ROLE_OUTPUT: "Output (TV/Projector)", ROLE_INPUT: "Input (Source Device)"}
                    ),
                    vol.Required(
                        CONF_CATCH_ALL_EVENT, default=info["suggested_event"]
                    ): str,
                    vol.Required(
                        CONF_ESPHOME_SERVICE, default=info["esphome_service"]
                    ): str,
                    vol.Required(CONF_TAP_ADDRESS, default=11): int,
                    vol.Optional(CONF_PHYSICAL_ADDRESS): str,
                    vol.Optional(CONF_DEVICE_ADDRESS): int,
                }
            ),
            description_placeholders={
                "device_name": info["device_name"],
                "tap_number": str(tap_num),
                "tap_total": str(total),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HdmiCecBridgeOptionsFlow:
        """Get the options flow handler."""
        return HdmiCecBridgeOptionsFlow(config_entry)


class HdmiCecBridgeOptionsFlow(config_entries.OptionsFlowWithConfigEntry):
    """Handle options flow for HDMI CEC Bridge — add/remove/edit taps."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__(config_entry)
        self._discovered: dict[str, dict[str, Any]] = {}
        self._action: str = ""
        self._selected_new: list[str] = []
        self._current_tap_index: int = 0
        self._new_taps: dict[str, dict[str, Any]] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show options menu."""
        if user_input is not None:
            action = user_input.get("action", "")
            if action == "add_taps":
                return await self.async_step_add_taps()
            if action == "remove_taps":
                return await self.async_step_remove_taps()
            if action == "edit_tap":
                return await self.async_step_select_edit_tap()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="add_taps"): vol.In(
                        {
                            "add_taps": "Add new CEC taps",
                            "remove_taps": "Remove existing taps",
                            "edit_tap": "Edit a tap's configuration",
                        }
                    ),
                }
            ),
        )

    async def async_step_add_taps(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Discover and add new taps."""
        self._discovered = _discover_cec_devices(self.hass)
        existing_devices = set(self.config_entry.data.get(CONF_TAPS, {}).keys())
        new_devices = {
            did: info
            for did, info in self._discovered.items()
            if did not in existing_devices
        }

        if not new_devices:
            return self.async_abort(reason="no_new_devices")

        if user_input is not None:
            self._selected_new = user_input.get("new_devices", [])
            if not self._selected_new:
                return self.async_abort(reason="no_devices_selected")
            self._current_tap_index = 0
            self._new_taps = {}
            return await self.async_step_configure_new_tap()

        device_options = {
            did: info["device_name"] for did, info in new_devices.items()
        }
        return self.async_show_form(
            step_id="add_taps",
            data_schema=vol.Schema(
                {
                    vol.Required("new_devices"): vol.All(
                        vol.Coerce(list),
                        [vol.In(device_options)],
                    ),
                }
            ),
        )

    async def async_step_configure_new_tap(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure a newly added tap."""
        if user_input is not None:
            device_id = self._selected_new[self._current_tap_index]
            self._new_taps[device_id] = {
                CONF_TAP_LABEL: user_input[CONF_TAP_LABEL],
                CONF_TAP_ROLE: user_input[CONF_TAP_ROLE],
                CONF_ESPHOME_DEVICE: self._discovered[device_id]["esphome_device"],
                CONF_ESPHOME_SERVICE: user_input.get(
                    CONF_ESPHOME_SERVICE,
                    self._discovered[device_id]["esphome_service"],
                ),
                CONF_CATCH_ALL_EVENT: user_input[CONF_CATCH_ALL_EVENT],
                CONF_TAP_ADDRESS: user_input[CONF_TAP_ADDRESS],
                CONF_PHYSICAL_ADDRESS: user_input.get(CONF_PHYSICAL_ADDRESS),
                CONF_DEVICE_ADDRESS: user_input.get(CONF_DEVICE_ADDRESS),
            }
            self._current_tap_index += 1

            if self._current_tap_index < len(self._selected_new):
                return await self.async_step_configure_new_tap()

            # Merge new taps into existing config
            updated_taps = dict(self.config_entry.data.get(CONF_TAPS, {}))
            updated_taps.update(self._new_taps)

            return self.async_create_entry(
                title="",
                data={CONF_TAPS: updated_taps},
            )

        device_id = self._selected_new[self._current_tap_index]
        info = self._discovered[device_id]
        return self.async_show_form(
            step_id="configure_new_tap",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TAP_LABEL, default=info["device_name"]): str,
                    vol.Required(CONF_TAP_ROLE, default=ROLE_INPUT): vol.In(
                        {ROLE_OUTPUT: "Output (TV/Projector)", ROLE_INPUT: "Input (Source Device)"}
                    ),
                    vol.Required(CONF_CATCH_ALL_EVENT, default=info["suggested_event"]): str,
                    vol.Required(CONF_ESPHOME_SERVICE, default=info["esphome_service"]): str,
                    vol.Required(CONF_TAP_ADDRESS, default=11): int,
                    vol.Optional(CONF_PHYSICAL_ADDRESS): str,
                    vol.Optional(CONF_DEVICE_ADDRESS): int,
                }
            ),
            description_placeholders={"device_name": info["device_name"]},
        )

    async def async_step_remove_taps(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove existing taps."""
        current_taps = self.config_entry.data.get(CONF_TAPS, {})

        if user_input is not None:
            to_remove = user_input.get("remove_devices", [])
            updated_taps = {
                did: cfg for did, cfg in current_taps.items() if did not in to_remove
            }

            # Validate remaining taps still have at least one input and output
            roles = [t[CONF_TAP_ROLE] for t in updated_taps.values()]
            if ROLE_OUTPUT not in roles or ROLE_INPUT not in roles:
                return self.async_show_form(
                    step_id="remove_taps",
                    data_schema=self._build_remove_schema(current_taps),
                    errors={"base": "need_input_and_output"},
                )

            return self.async_create_entry(
                title="",
                data={CONF_TAPS: updated_taps},
            )

        return self.async_show_form(
            step_id="remove_taps",
            data_schema=self._build_remove_schema(current_taps),
        )

    def _build_remove_schema(
        self, taps: dict[str, dict[str, Any]]
    ) -> vol.Schema:
        """Build schema for tap removal."""
        tap_options = {
            did: f"{cfg[CONF_TAP_LABEL]} ({cfg[CONF_TAP_ROLE]})"
            for did, cfg in taps.items()
        }
        return vol.Schema(
            {
                vol.Required("remove_devices"): vol.All(
                    vol.Coerce(list),
                    [vol.In(tap_options)],
                ),
            }
        )

    async def async_step_select_edit_tap(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select a tap to edit."""
        current_taps = self.config_entry.data.get(CONF_TAPS, {})

        if user_input is not None:
            self._edit_device_id = user_input["edit_device"]
            return await self.async_step_edit_tap()

        tap_options = {
            did: f"{cfg[CONF_TAP_LABEL]} ({cfg[CONF_TAP_ROLE]})"
            for did, cfg in current_taps.items()
        }
        return self.async_show_form(
            step_id="select_edit_tap",
            data_schema=vol.Schema(
                {vol.Required("edit_device"): vol.In(tap_options)}
            ),
        )

    async def async_step_edit_tap(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit a specific tap's configuration."""
        current_taps = self.config_entry.data.get(CONF_TAPS, {})
        tap = current_taps[self._edit_device_id]

        if user_input is not None:
            updated_taps = dict(current_taps)
            updated_taps[self._edit_device_id] = {
                CONF_TAP_LABEL: user_input[CONF_TAP_LABEL],
                CONF_TAP_ROLE: user_input[CONF_TAP_ROLE],
                CONF_ESPHOME_DEVICE: tap[CONF_ESPHOME_DEVICE],
                CONF_ESPHOME_SERVICE: user_input[CONF_ESPHOME_SERVICE],
                CONF_CATCH_ALL_EVENT: user_input[CONF_CATCH_ALL_EVENT],
                CONF_TAP_ADDRESS: user_input[CONF_TAP_ADDRESS],
                CONF_PHYSICAL_ADDRESS: user_input.get(CONF_PHYSICAL_ADDRESS),
                CONF_DEVICE_ADDRESS: user_input.get(CONF_DEVICE_ADDRESS),
            }

            return self.async_create_entry(
                title="",
                data={CONF_TAPS: updated_taps},
            )

        return self.async_show_form(
            step_id="edit_tap",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TAP_LABEL, default=tap[CONF_TAP_LABEL]): str,
                    vol.Required(CONF_TAP_ROLE, default=tap[CONF_TAP_ROLE]): vol.In(
                        {ROLE_OUTPUT: "Output (TV/Projector)", ROLE_INPUT: "Input (Source Device)"}
                    ),
                    vol.Required(
                        CONF_CATCH_ALL_EVENT, default=tap[CONF_CATCH_ALL_EVENT]
                    ): str,
                    vol.Required(
                        CONF_ESPHOME_SERVICE, default=tap[CONF_ESPHOME_SERVICE]
                    ): str,
                    vol.Required(CONF_TAP_ADDRESS, default=tap[CONF_TAP_ADDRESS]): int,
                    vol.Optional(
                        CONF_PHYSICAL_ADDRESS,
                        default=tap.get(CONF_PHYSICAL_ADDRESS, ""),
                    ): str,
                    vol.Optional(
                        CONF_DEVICE_ADDRESS,
                        default=tap.get(CONF_DEVICE_ADDRESS),
                    ): vol.Any(int, None),
                }
            ),
            description_placeholders={"device_name": tap[CONF_TAP_LABEL]},
        )
