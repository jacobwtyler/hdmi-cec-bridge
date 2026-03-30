# HDMI CEC Bridge

A Home Assistant custom integration that bridges isolated HDMI CEC bus segments through ESPHome CEC tap devices.

## Problem

HDMI matrix switches (like the Feintech) isolate each input's CEC bus from the output. Source devices (Apple TV, game consoles) can't communicate CEC commands (wake, standby, active source) to the TV/projector on the other side of the switch.

## Solution

With ESP32 CEC taps (using the [Palakis `esphome-hdmi-cec`](https://github.com/Palakis/esphome-hdmi-cec) component) on each HDMI port, this integration:

- **Auto-discovers** ESPHome CEC tap devices in Home Assistant
- **Relays CEC messages** between isolated bus segments via configurable rules
- **Tracks state** — TV power, active source, per-tap CEC activity
- **Provides controls** — wake TV, standby, switch inputs, poll power status
- **Prevents loops** — source address filtering + debounce + direction restrictions

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CEC Bridge Coordinator                     │
│                                                               │
│  Event Listeners (one per tap):                               │
│    hass.bus.async_listen("esphome.hdmi_cec_output", ...)      │
│    hass.bus.async_listen("esphome.hdmi_cec_atv", ...)         │
│                                                               │
│  On event:                                                    │
│    1. Identify source tap                                     │
│    2. Parse opcode, source, destination                       │
│    3. Update tap's last_event sensor                          │
│    4. Skip if source == tap's own address (self-echo)         │
│    5. Evaluate relay rules (check switch states)              │
│    6. If match: call target tap's ESPHome send service        │
│    7. Update relay_count, tv_power, active_source             │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. ESPHome CEC Taps

Each tap needs the [Palakis `esphome-hdmi-cec`](https://github.com/Palakis/esphome-hdmi-cec) external component with:

- `promiscuous_mode: true`
- A catch-all `on_message` handler that fires a `homeassistant.event`
- An `api.services` entry named `hdmi_cec_send`

#### Minimal ESPHome YAML Example

```yaml
substitutions:
  name: cec-my-tap
  friendly_name: CEC Tap - My Device

esphome:
  name: ${name}
  friendly_name: ${friendly_name}

esp32:
  board: esp32-c3-devkitm-1
  variant: ESP32C3
  framework:
    type: esp-idf

logger:

api:
  encryption:
    key: !secret api_key
  services:
    - service: hdmi_cec_send
      variables:
        cec_destination: int
        cec_data: int[]
      then:
        - hdmi_cec.send:
            destination: !lambda "return static_cast<unsigned char>(cec_destination);"
            data: !lambda |-
              std::vector<unsigned char> vec;
              for (int i : cec_data) vec.push_back(static_cast<unsigned char>(i));
              return vec;

ota:
  - platform: esphome

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

external_components:
  - source: github://Palakis/esphome-hdmi-cec

hdmi_cec:
  pin: GPIO10
  address: 0x0B          # Choose an unused CEC logical address
  physical_address: 0x1110  # Set appropriately for your topology
  osd_name: "CEC-Tap"
  promiscuous_mode: true

  on_message:
    # Catch-all: fire HA event with all CEC data
    - then:
        - lambda: |-
            id(cec_raw_message).publish_state(
              hdmi_cec::Frame(source, destination, data).to_string(true)
            );
            id(cec_translated_message).publish_state(
              hdmi_cec::Frame(source, destination, data).to_string()
            );
        - homeassistant.event:
            event: esphome.hdmi_cec_my_tap  # Must match catch_all_event in bridge config
            data:
              source: !lambda return std::to_string(source);
              destination: !lambda return std::to_string(destination);
              opcode: !lambda |-
                return data.size() ? std::to_string(data[0]) : std::string("0");
              raw: !lambda return hdmi_cec::Frame(source, destination, data).to_string(true);
              translated: !lambda return hdmi_cec::Frame(source, destination, data).to_string();

text_sensor:
  - platform: template
    name: "HDMI CEC Raw Message"
    id: cec_raw_message
    update_interval: never

  - platform: template
    name: "HDMI CEC Translated Message"
    id: cec_translated_message
    update_interval: never
```

### 2. ESPHome Service Calls

For each CEC tap in the ESPHome integration:
1. Go to **Settings → Integrations → ESPHome**
2. Click the tap device → **Options**
3. Enable **"Allow the device to make Home Assistant service calls"**

### 3. HACS

Install [HACS](https://hacs.xyz/) if not already installed.

## Installation

1. In HACS, click the **three dots** menu → **Custom repositories**
2. Add this repository URL, category: **Integration**
3. Click **Install**
4. Restart Home Assistant

## Configuration

1. Go to **Settings → Integrations → Add Integration**
2. Search for **"HDMI CEC Bridge"**
3. The integration auto-discovers ESPHome devices with CEC entities
4. Select which taps to include
5. Configure each tap:
   - **Label**: Friendly name (e.g., "Apple TV", "Projector")
   - **Role**: Output (TV/projector side) or Input (source device side)
   - **Catch-all event**: The ESPHome event name (e.g., `esphome.hdmi_cec_output`)
   - **ESPHome service**: The send service (e.g., `cec_output_tap_hdmi_cec_send`)
   - **Tap address**: The ESP32's CEC logical address
   - **Physical address**: (Input taps) The source device's CEC PA (e.g., `1.1.0.0`)
   - **Device address**: (Input taps, optional) The source device's CEC logical address

## Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.{bridge}_tv_power` | TV power state: on/standby/to_on/to_standby/unknown |
| `sensor.{bridge}_active_source` | Label of the currently active input |
| `sensor.{bridge}_relay_count` | Total relayed CEC frames since last reload |
| `sensor.{bridge}_{tap}_last_event` | Last CEC event on each tap (one per tap) |

### Buttons

| Entity | Action |
|--------|--------|
| `button.{bridge}_wake_tv` | Send Image View On to TV |
| `button.{bridge}_standby_all` | Send Standby broadcast |
| `button.{bridge}_request_tv_power` | Poll TV power status |
| `button.{bridge}_request_all_power` | Poll all devices for power status |
| `button.{bridge}_switch_to_{input}` | Switch to a specific input (one per input tap) |

### Select

| Entity | Description |
|--------|-------------|
| `select.{bridge}_active_input` | Dropdown to choose the active input |

### Switches (Relay Rules)

| Entity | Default | Description |
|--------|---------|-------------|
| `switch.{bridge}_relay_wake_to_output` | ON | Relay wake commands from inputs to output |
| `switch.{bridge}_relay_standby_to_output` | ON | Relay standby from inputs to output |
| `switch.{bridge}_relay_power_status_to_inputs` | ON | Relay power status from output to active input |
| `switch.{bridge}_relay_power_request_to_output` | ON | Relay power requests from inputs to output |
| `switch.{bridge}_relay_active_source_to_output` | OFF | Relay Active Source from inputs to output |

## Loop Prevention

1. **Source address filtering**: If event source matches the tap's own CEC address → skip (self-echo)
2. **Debounce**: 500ms cooldown per (opcode, direction) pair
3. **Direction restriction**: Input taps only relay TO output; output taps only relay TO inputs

## Options Flow

After initial setup, go to the integration's **Options** to:
- Add new CEC taps (re-discovers available devices)
- Remove existing taps
- Edit tap configuration (role, label, addresses)

## License

MIT
