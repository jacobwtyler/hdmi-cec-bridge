"""Coordinator for the HDMI CEC Bridge — event listener and relay engine."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CEC_ADDR_BROADCAST,
    CEC_ADDR_TV,
    CEC_OPCODE_ACTIVE_SOURCE,
    CEC_OPCODE_GIVE_POWER_STATUS,
    CEC_OPCODE_IMAGE_VIEW_ON,
    CEC_OPCODE_REPORT_POWER_STATUS,
    CEC_OPCODE_STANDBY,
    CEC_OPCODE_TEXT_VIEW_ON,
    DEBOUNCE_MS,
    DEFAULT_RELAY_RULES,
    DOMAIN,
    OPCODE_NAMES,
    POWER_STATUS_MAP,
    POWER_UNKNOWN,
    ROLE_INPUT,
    ROLE_OUTPUT,
    RULE_ACTIVE_SOURCE_TO_OUTPUT,
    RULE_POWER_REQUEST_TO_OUTPUT,
    RULE_POWER_STATUS_TO_INPUTS,
    RULE_STANDBY_TO_OUTPUT,
    RULE_WAKE_TO_OUTPUT,
)
from .models import CecFrame, CecTap

_LOGGER = logging.getLogger(__name__)

SIGNAL_CEC_EVENT = f"{DOMAIN}_cec_event"
SIGNAL_STATE_UPDATE = f"{DOMAIN}_state_update"


class CecBridgeCoordinator:
    """Manages event listeners, relay logic, and state tracking for a CEC bridge."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        bridge_name: str,
        taps: dict[str, CecTap],
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry_id = entry_id
        self.bridge_name = bridge_name
        self.taps = taps

        # State
        self.tv_power: str = POWER_UNKNOWN
        self.active_source_label: str = "unknown"
        self.active_source_pa: str | None = None
        self.active_input_device_id: str | None = None
        self.relay_count: int = 0
        self.last_relay_direction: str = ""
        self.last_relay_opcode: str = ""
        self.last_relay_time: str = ""

        # Per-tap last event state: {device_id: CecFrame}
        self.tap_last_events: dict[str, CecFrame | None] = {
            did: None for did in taps
        }

        # Relay rule states (loaded from RestoreEntity switches)
        self.relay_rules: dict[str, bool] = dict(DEFAULT_RELAY_RULES)

        # Loop prevention: {(opcode, direction): last_relay_timestamp_ms}
        self._debounce: dict[tuple[int, str], float] = {}

        # Listener unsubscribes
        self._unsub_listeners: list[CALLBACK_TYPE] = []

    @property
    def slug(self) -> str:
        """Return a slug for entity ID prefixes."""
        return self.bridge_name.lower().replace(" ", "_").replace("-", "_")

    @property
    def output_taps(self) -> list[CecTap]:
        """Return all output taps."""
        return [t for t in self.taps.values() if t.is_output]

    @property
    def input_taps(self) -> list[CecTap]:
        """Return all input taps."""
        return [t for t in self.taps.values() if t.is_input]

    @property
    def primary_output(self) -> CecTap | None:
        """Return the first output tap (primary)."""
        outputs = self.output_taps
        return outputs[0] if outputs else None

    def get_active_input_tap(self) -> CecTap | None:
        """Return the currently active input tap."""
        if self.active_input_device_id:
            return self.taps.get(self.active_input_device_id)
        # Fallback to first input
        inputs = self.input_taps
        return inputs[0] if inputs else None

    async def async_start(self) -> None:
        """Start listening to CEC events from all taps."""
        for device_id, tap in self.taps.items():
            unsub = self.hass.bus.async_listen(
                tap.catch_all_event,
                self._make_event_handler(device_id, tap),
            )
            self._unsub_listeners.append(unsub)
            _LOGGER.info(
                "CEC Bridge: Listening to %s for tap '%s'",
                tap.catch_all_event,
                tap.label,
            )

    async def async_stop(self) -> None:
        """Stop all event listeners."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        _LOGGER.info("CEC Bridge: All listeners stopped")

    def _make_event_handler(
        self, device_id: str, tap: CecTap
    ) -> Callable[[Event], None]:
        """Create an event handler closure for a specific tap."""

        @callback
        def handle_cec_event(event: Event) -> None:
            """Handle an incoming CEC event from this tap."""
            frame = CecFrame.from_event_data(event.data, device_id)

            # Update per-tap last event
            self.tap_last_events[device_id] = frame

            # Signal sensors to update
            async_dispatcher_send(
                self.hass,
                f"{SIGNAL_CEC_EVENT}_{self.entry_id}_{device_id}",
                frame,
            )

            # Loop guard: skip if source is the tap's own address (self-echo)
            if frame.source == tap.tap_address:
                _LOGGER.debug(
                    "CEC Bridge: Skipping self-echo from tap '%s' (addr 0x%02X)",
                    tap.label,
                    tap.tap_address,
                )
                return

            # Process based on opcode
            self._process_frame(tap, frame)

        return handle_cec_event

    def _process_frame(self, source_tap: CecTap, frame: CecFrame) -> None:
        """Process a CEC frame and evaluate relay rules."""
        opcode = frame.opcode

        # --- State tracking (always runs, regardless of relay rules) ---

        # Track TV power from output bus
        if source_tap.is_output and opcode == CEC_OPCODE_REPORT_POWER_STATUS:
            if frame.source == CEC_ADDR_TV:
                status_byte = self._extract_param_byte(frame)
                self.tv_power = POWER_STATUS_MAP.get(status_byte, POWER_UNKNOWN)
                async_dispatcher_send(
                    self.hass, f"{SIGNAL_STATE_UPDATE}_{self.entry_id}"
                )

        # Track active source
        if opcode == CEC_OPCODE_ACTIVE_SOURCE:
            self._handle_active_source(source_tap, frame)

        # --- Relay evaluation ---

        if source_tap.is_input:
            self._evaluate_input_relay(source_tap, frame)
        elif source_tap.is_output:
            self._evaluate_output_relay(source_tap, frame)

    def _evaluate_input_relay(self, source_tap: CecTap, frame: CecFrame) -> None:
        """Evaluate relay rules for frames from an input tap → output."""
        opcode = frame.opcode
        output = self.primary_output
        if not output:
            return

        # Rule: Wake to output
        if opcode in (CEC_OPCODE_IMAGE_VIEW_ON, CEC_OPCODE_TEXT_VIEW_ON):
            if self.relay_rules.get(RULE_WAKE_TO_OUTPUT, False):
                self._relay(
                    output,
                    CEC_ADDR_TV,
                    [CEC_OPCODE_IMAGE_VIEW_ON],
                    opcode,
                    "input_to_output",
                )

        # Rule: Standby to output
        elif opcode == CEC_OPCODE_STANDBY:
            if self.relay_rules.get(RULE_STANDBY_TO_OUTPUT, False):
                # Only relay if source is the tap's connected device
                if source_tap.device_address is None or frame.source == source_tap.device_address:
                    self._relay(
                        output,
                        CEC_ADDR_BROADCAST,
                        [CEC_OPCODE_STANDBY],
                        opcode,
                        "input_to_output",
                    )

        # Rule: Power request to output
        elif opcode == CEC_OPCODE_GIVE_POWER_STATUS:
            if self.relay_rules.get(RULE_POWER_REQUEST_TO_OUTPUT, False):
                self._relay(
                    output,
                    CEC_ADDR_TV,
                    [CEC_OPCODE_GIVE_POWER_STATUS],
                    opcode,
                    "input_to_output",
                )

        # Rule: Active Source to output
        elif opcode == CEC_OPCODE_ACTIVE_SOURCE:
            if self.relay_rules.get(RULE_ACTIVE_SOURCE_TO_OUTPUT, False):
                pa_bytes = source_tap.pa_bytes
                if pa_bytes:
                    self._relay(
                        output,
                        CEC_ADDR_BROADCAST,
                        [CEC_OPCODE_ACTIVE_SOURCE] + pa_bytes,
                        opcode,
                        "input_to_output",
                    )

    def _evaluate_output_relay(self, source_tap: CecTap, frame: CecFrame) -> None:
        """Evaluate relay rules for frames from the output tap → active input."""
        opcode = frame.opcode

        # Rule: Power status to active input
        if opcode == CEC_OPCODE_REPORT_POWER_STATUS:
            if self.relay_rules.get(RULE_POWER_STATUS_TO_INPUTS, False):
                active_input = self.get_active_input_tap()
                if active_input and active_input.device_address is not None:
                    status_byte = self._extract_param_byte(frame)
                    self._relay(
                        active_input,
                        active_input.device_address,
                        [CEC_OPCODE_REPORT_POWER_STATUS, status_byte],
                        opcode,
                        "output_to_input",
                    )

    def _relay(
        self,
        target_tap: CecTap,
        destination: int,
        data: list[int],
        opcode: int,
        direction: str,
    ) -> None:
        """Send a CEC frame via an ESPHome service call, with debounce."""
        now_ms = time.monotonic() * 1000
        key = (opcode, direction)
        last = self._debounce.get(key, 0)
        if now_ms - last < DEBOUNCE_MS:
            _LOGGER.debug(
                "CEC Bridge: Debounce skip — opcode 0x%02X %s (%.0fms ago)",
                opcode,
                direction,
                now_ms - last,
            )
            return

        self._debounce[key] = now_ms

        _LOGGER.info(
            "CEC Bridge: Relay %s → %s dest=0x%02X data=%s",
            direction,
            target_tap.label,
            destination,
            [f"0x{b:02X}" for b in data],
        )

        self.hass.async_create_task(
            self.hass.services.async_call(
                "esphome",
                target_tap.esphome_service,
                {
                    "cec_destination": destination,
                    "cec_data": data,
                },
            )
        )

        # Update relay counter
        self.relay_count += 1
        self.last_relay_direction = direction
        self.last_relay_opcode = OPCODE_NAMES.get(opcode, f"0x{opcode:02X}")
        self.last_relay_time = time.strftime("%Y-%m-%dT%H:%M:%S")
        async_dispatcher_send(
            self.hass, f"{SIGNAL_STATE_UPDATE}_{self.entry_id}"
        )

    def _handle_active_source(self, source_tap: CecTap, frame: CecFrame) -> None:
        """Handle Active Source opcode — update tracking."""
        # Try to match PA to an input tap
        # The PA is in the event's raw data, but we can also check which input tap fired it
        if source_tap.is_input:
            self.active_source_label = source_tap.label
            self.active_source_pa = source_tap.physical_address
            self.active_input_device_id = source_tap.device_id
            async_dispatcher_send(
                self.hass, f"{SIGNAL_STATE_UPDATE}_{self.entry_id}"
            )

    def set_active_input(self, device_id: str) -> None:
        """Set the active input (from select entity)."""
        tap = self.taps.get(device_id)
        if tap and tap.is_input:
            self.active_input_device_id = device_id
            self.active_source_label = tap.label
            self.active_source_pa = tap.physical_address
            async_dispatcher_send(
                self.hass, f"{SIGNAL_STATE_UPDATE}_{self.entry_id}"
            )

    async def async_send_active_source(self, input_tap: CecTap) -> None:
        """Send Active Source for a given input tap via the output tap."""
        output = self.primary_output
        if not output or not input_tap.pa_bytes:
            return

        await self.hass.services.async_call(
            "esphome",
            output.esphome_service,
            {
                "cec_destination": CEC_ADDR_BROADCAST,
                "cec_data": [CEC_OPCODE_ACTIVE_SOURCE] + input_tap.pa_bytes,
            },
        )

        # Update tracking
        self.set_active_input(input_tap.device_id)

    async def async_send_cec(
        self, tap: CecTap, destination: int, data: list[int]
    ) -> None:
        """Send a CEC frame via a tap's ESPHome service."""
        await self.hass.services.async_call(
            "esphome",
            tap.esphome_service,
            {
                "cec_destination": destination,
                "cec_data": data,
            },
        )

    @staticmethod
    def _extract_param_byte(frame: CecFrame) -> int:
        """Extract the first parameter byte from a frame's raw string.

        Falls back to 0 if not parseable. The raw format from ESPHome is like:
        "09:00:90:01" where bytes after opcode are parameters.
        """
        # Try parsing from raw hex string
        raw = frame.raw
        if raw:
            parts = raw.split(":")
            # Format: src:dst:opcode:param1:param2...
            if len(parts) >= 4:
                try:
                    return int(parts[3], 16)
                except ValueError:
                    pass
        return 0
