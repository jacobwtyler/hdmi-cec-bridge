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

# CEC opcodes (hex values per HDMI CEC 1.4 / kernel cec-header.h)
CEC_OPCODE_FEATURE_ABORT = 0x00
CEC_OPCODE_IMAGE_VIEW_ON = 0x04
CEC_OPCODE_TEXT_VIEW_ON = 0x0D
CEC_OPCODE_GIVE_TUNER_DEVICE_STATUS = 0x08
CEC_OPCODE_RECORD_ON = 0x09
CEC_OPCODE_RECORD_OFF = 0x0B
CEC_OPCODE_SET_MENU_LANGUAGE = 0x32
CEC_OPCODE_STANDBY = 0x36
CEC_OPCODE_USER_CONTROL_PRESSED = 0x44
CEC_OPCODE_USER_CONTROL_RELEASED = 0x45
CEC_OPCODE_GIVE_OSD_NAME = 0x46
CEC_OPCODE_SET_OSD_NAME = 0x47
CEC_OPCODE_SYSTEM_AUDIO_MODE_REQUEST = 0x70
CEC_OPCODE_GIVE_AUDIO_STATUS = 0x71
CEC_OPCODE_SET_SYSTEM_AUDIO_MODE = 0x72
CEC_OPCODE_REPORT_AUDIO_STATUS = 0x7A
CEC_OPCODE_ROUTING_CHANGE = 0x80
CEC_OPCODE_ACTIVE_SOURCE = 0x82
CEC_OPCODE_GIVE_PHYSICAL_ADDRESS = 0x83
CEC_OPCODE_REPORT_PHYSICAL_ADDRESS = 0x84
CEC_OPCODE_REQUEST_ACTIVE_SOURCE = 0x85
CEC_OPCODE_SET_STREAM_PATH = 0x86
CEC_OPCODE_DEVICE_VENDOR_ID = 0x87
CEC_OPCODE_VENDOR_COMMAND = 0x89
CEC_OPCODE_GIVE_DEVICE_VENDOR_ID = 0x8C
CEC_OPCODE_MENU_REQUEST = 0x8D
CEC_OPCODE_MENU_STATUS = 0x8E
CEC_OPCODE_GIVE_POWER_STATUS = 0x8F
CEC_OPCODE_REPORT_POWER_STATUS = 0x90
CEC_OPCODE_GET_MENU_LANGUAGE = 0x91
CEC_OPCODE_INACTIVE_SOURCE = 0x9D
CEC_OPCODE_CEC_VERSION = 0x9E
CEC_OPCODE_GET_CEC_VERSION = 0x9F
CEC_OPCODE_REPORT_SHORT_AUDIO_DESCRIPTOR = 0xA3
CEC_OPCODE_REQUEST_SHORT_AUDIO_DESCRIPTOR = 0xA4
CEC_OPCODE_GIVE_FEATURES = 0xA5
CEC_OPCODE_REPORT_FEATURES = 0xA6
CEC_OPCODE_INITIATE_ARC = 0xC0
CEC_OPCODE_REPORT_ARC_INITIATED = 0xC1
CEC_OPCODE_REPORT_ARC_TERMINATED = 0xC2
CEC_OPCODE_REQUEST_ARC_INITIATION = 0xC3
CEC_OPCODE_REQUEST_ARC_TERMINATION = 0xC4
CEC_OPCODE_TERMINATE_ARC = 0xC5
CEC_OPCODE_ABORT = 0xFF

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
    0x00: "Feature Abort",
    0x04: "Image View On",
    0x08: "Give Tuner Device Status",
    0x09: "Record On",
    0x0B: "Record Off",
    0x0D: "Text View On",
    0x32: "Set Menu Language",
    0x36: "Standby",
    0x44: "User Control Pressed",
    0x45: "User Control Released",
    0x46: "Give OSD Name",
    0x47: "Set OSD Name",
    0x70: "System Audio Mode Request",
    0x71: "Give Audio Status",
    0x72: "Set System Audio Mode",
    0x7A: "Report Audio Status",
    0x80: "Routing Change",
    0x82: "Active Source",
    0x83: "Give Physical Address",
    0x84: "Report Physical Address",
    0x85: "Request Active Source",
    0x86: "Set Stream Path",
    0x87: "Device Vendor ID",
    0x89: "Vendor Command",
    0x8C: "Give Device Vendor ID",
    0x8D: "Menu Request",
    0x8E: "Menu Status",
    0x8F: "Give Device Power Status",
    0x90: "Report Power Status",
    0x91: "Get Menu Language",
    0x9D: "Inactive Source",
    0x9E: "CEC Version",
    0x9F: "Get CEC Version",
    0xA3: "Report Short Audio Descriptor",
    0xA4: "Request Short Audio Descriptor",
    0xA5: "Give Features",
    0xA6: "Report Features",
    0xC0: "Initiate ARC",
    0xC1: "Report ARC Initiated",
    0xC2: "Report ARC Terminated",
    0xC3: "Request ARC Initiation",
    0xC4: "Request ARC Termination",
    0xC5: "Terminate ARC",
    0xFF: "Abort",
}
