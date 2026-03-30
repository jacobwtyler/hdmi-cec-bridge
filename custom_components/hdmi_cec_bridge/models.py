"""Data models for the HDMI CEC Bridge integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import OPCODE_NAMES, ROLE_INPUT, ROLE_OUTPUT


@dataclass
class CecTap:
    """Represents an ESPHome CEC tap device."""

    device_id: str
    label: str
    role: str  # "output" or "input"
    esphome_device: str
    esphome_service: str
    catch_all_event: str
    tap_address: int
    physical_address: str | None = None
    device_address: int | None = None

    @property
    def is_output(self) -> bool:
        """Return True if this is an output tap."""
        return self.role == ROLE_OUTPUT

    @property
    def is_input(self) -> bool:
        """Return True if this is an input tap."""
        return self.role == ROLE_INPUT

    @property
    def slug(self) -> str:
        """Return a slug-safe version of the label."""
        return self.label.lower().replace(" ", "_").replace("-", "_")

    @property
    def pa_bytes(self) -> list[int] | None:
        """Return physical address as two bytes for CEC frames, or None."""
        if not self.physical_address:
            return None
        parts = self.physical_address.split(".")
        if len(parts) != 4:
            return None
        try:
            nibbles = [int(p) & 0x0F for p in parts]
            high = (nibbles[0] << 4) | nibbles[1]
            low = (nibbles[2] << 4) | nibbles[3]
            return [high, low]
        except (ValueError, IndexError):
            return None

    @classmethod
    def from_config(cls, device_id: str, config: dict[str, Any]) -> CecTap:
        """Create a CecTap from stored config data."""
        return cls(
            device_id=device_id,
            label=config["label"],
            role=config["role"],
            esphome_device=config["esphome_device"],
            esphome_service=config["esphome_service"],
            catch_all_event=config["catch_all_event"],
            tap_address=config["tap_address"],
            physical_address=config.get("physical_address"),
            device_address=config.get("device_address"),
        )


@dataclass
class CecFrame:
    """Represents a parsed CEC frame from an event."""

    source: int
    destination: int
    opcode: int
    raw: str = ""
    translated: str = ""
    tap_device_id: str = ""
    data_bytes: list[int] = field(default_factory=list)

    @property
    def opcode_name(self) -> str:
        """Return human-readable opcode name."""
        return OPCODE_NAMES.get(self.opcode, f"Unknown (0x{self.opcode:02X})")

    @property
    def opcode_hex(self) -> str:
        """Return opcode as hex string."""
        return f"0x{self.opcode:02X}"

    @property
    def summary(self) -> str:
        """Return a human-readable summary of this frame."""
        return f"{self.opcode_name} from 0x{self.source:02X} to 0x{self.destination:02X}"

    @classmethod
    def from_event_data(cls, data: dict[str, Any], tap_device_id: str = "") -> CecFrame:
        """Parse a CecFrame from an ESPHome event's data dict."""
        source = int(data.get("source", 0))
        destination = int(data.get("destination", 0))
        opcode = int(data.get("opcode", 0))
        raw = data.get("raw", "")
        translated = data.get("translated", "")
        return cls(
            source=source,
            destination=destination,
            opcode=opcode,
            raw=raw,
            translated=translated,
            tap_device_id=tap_device_id,
        )
