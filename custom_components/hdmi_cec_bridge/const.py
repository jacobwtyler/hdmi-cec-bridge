"""Constants for the HDMI CEC Bridge integration."""

DOMAIN = "hdmi_cec_bridge"

# Config keys
CONF_TAPS = "taps"
CONF_BRIDGE_NAME = "name"
CONF_TAP_LABEL = "label"
CONF_TAP_ROLE = "role"
CONF_ESPHOME_DEVICE = "esphome_device"
CONF_ESPHOME_SERVICE = "esphome_service"
CONF_CATCH_ALL_EVENT = "catch_all_event"
CONF_TAP_ADDRESS = "tap_address"
CONF_PHYSICAL_ADDRESS = "physical_address"
CONF_DEVICE_ADDRESS = "device_address"

# Tap roles
ROLE_OUTPUT = "output"
ROLE_INPUT = "input"

# Relay rule keys
RULE_WAKE_TO_OUTPUT = "relay_wake_to_output"
RULE_STANDBY_TO_OUTPUT = "relay_standby_to_output"
RULE_POWER_STATUS_TO_INPUTS = "relay_power_status_to_inputs"
RULE_POWER_REQUEST_TO_OUTPUT = "relay_power_request_to_output"
RULE_ACTIVE_SOURCE_TO_OUTPUT = "relay_active_source_to_output"

DEFAULT_RELAY_RULES = {
    RULE_WAKE_TO_OUTPUT: True,
    RULE_STANDBY_TO_OUTPUT: True,
    RULE_POWER_STATUS_TO_INPUTS: True,
    RULE_POWER_REQUEST_TO_OUTPUT: True,
    RULE_ACTIVE_SOURCE_TO_OUTPUT: False,
}

RELAY_RULE_DESCRIPTIONS = {
    RULE_WAKE_TO_OUTPUT: "Relay wake (Image View On) from input taps to output",
    RULE_STANDBY_TO_OUTPUT: "Relay standby from input taps to output",
    RULE_POWER_STATUS_TO_INPUTS: "Relay power status from output to active input",
    RULE_POWER_REQUEST_TO_OUTPUT: "Relay power status requests from inputs to output",
    RULE_ACTIVE_SOURCE_TO_OUTPUT: "Relay Active Source from inputs to output (may cause loops)",
}

# Loop prevention
DEBOUNCE_MS = 500

# CEC opcodes
CEC_OPCODE_IMAGE_VIEW_ON = 0x04
CEC_OPCODE_TEXT_VIEW_ON = 0x0D
CEC_OPCODE_STANDBY = 0x36
CEC_OPCODE_USER_CONTROL_PRESSED = 0x44
CEC_OPCODE_USER_CONTROL_RELEASED = 0x45
CEC_OPCODE_GIVE_AUDIO_STATUS = 0x71
CEC_OPCODE_REPORT_AUDIO_STATUS = 0x7A
CEC_OPCODE_ROUTING_CHANGE = 0x80
CEC_OPCODE_ACTIVE_SOURCE = 0x82
CEC_OPCODE_REQUEST_ACTIVE_SOURCE = 0x85
CEC_OPCODE_SET_STREAM_PATH = 0x86
CEC_OPCODE_GIVE_POWER_STATUS = 0x8F
CEC_OPCODE_REPORT_POWER_STATUS = 0x90
CEC_OPCODE_INACTIVE_SOURCE = 0x9D

# CEC addresses
CEC_ADDR_TV = 0x00
CEC_ADDR_AUDIO_SYSTEM = 0x05
CEC_ADDR_BROADCAST = 0x0F

# CEC power states
POWER_ON = "on"
POWER_STANDBY = "standby"
POWER_TO_ON = "to_on"
POWER_TO_STANDBY = "to_standby"
POWER_UNKNOWN = "unknown"

POWER_STATUS_MAP = {
    0x00: POWER_ON,
    0x01: POWER_STANDBY,
    0x02: POWER_TO_STANDBY,
    0x03: POWER_TO_ON,
}

OPCODE_NAMES = {
    0x04: "Image View On",
    0x0D: "Text View On",
    0x36: "Standby",
    0x44: "User Control Pressed",
    0x45: "User Control Released",
    0x71: "Give Audio Status",
    0x7A: "Report Audio Status",
    0x80: "Routing Change",
    0x82: "Active Source",
    0x85: "Request Active Source",
    0x86: "Set Stream Path",
    0x8F: "Give Device Power Status",
    0x90: "Report Power Status",
    0x9D: "Inactive Source",
    0xC0: "Initiate ARC",
    0xC1: "Report ARC Initiated",
    0xC2: "Report ARC Terminated",
    0xC3: "Request ARC Initiation",
    0xC4: "Request ARC Termination",
}
