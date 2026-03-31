# HDMI CEC Bridge

A Home Assistant custom integration (HACS) that bridges isolated HDMI CEC bus segments through ESPHome CEC tap devices.

## Problem

HDMI matrix switches (like the Feintech) isolate each input's CEC bus from the output. Source devices (Apple TV, game consoles) can't communicate CEC commands (wake, standby, active source) to the TV/projector on the other side of the switch.

## Solution

With ESP32 CEC taps (using the [Palakis `esphome-hdmi-cec`](https://github.com/Palakis/esphome-hdmi-cec) component) on each HDMI port, this integration:

- **Auto-discovers** ESPHome CEC tap devices in Home Assistant
- **Relays CEC messages** between isolated bus segments via configurable rules
- **Tracks state** -- TV power, active source, audio volume, per-tap CEC activity
- **Provides controls** -- wake TV, standby, switch inputs, volume slider, poll power/audio status
- **Prevents loops** -- source address filtering + debounce + direction restrictions

## Architecture

```
                         HDMI Matrix Switch (e.g. Feintech)
                    ┌──────────────────────────────────────────┐
  Apple TV ──CEC──▶ │ Input 1 ─┐                               │
                    │          │   ┌──────────┐                │
  Nintendo ──CEC──▶ │ Input 2 ─┼──▶│ Crossbar │──▶ Output ─CEC──▶ TV/Projector
                    │          │   └──────────┘                │
  RetroPie ──CEC──▶ │ Input 3 ─┘                               │
                    └──────────────────────────────────────────┘
                         ▲                                ▲
                         │  CEC bus isolated per port     │
                    ESP32 CEC Taps                   ESP32 CEC Tap
                    (input taps)                     (output tap)
                         │                                │
                         ▼                                ▼
                    ┌──────────────────────────────────────────┐
                    │         Home Assistant                     │
                    │    HDMI CEC Bridge Integration             │
                    │                                           │
                    │  - Relays CEC between taps               │
                    │  - Tracks TV power, active source         │
                    │  - Provides buttons, selects, switches    │
                    └──────────────────────────────────────────┘
```

---

## Hardware Setup

### Bill of Materials (per tap)

| Component | Notes |
|-----------|-------|
| **ESP32-C3 SuperMini** | Compact, inexpensive, ESP-IDF compatible. Any ESP32 variant works. |
| **HDMI breakout board** | Female-to-female passthrough with pin headers exposing CEC (pin 13), GND, and 5V/HPD |
| **Jumper wires** | 3 wires: CEC signal, GND, and optionally 5V for power |

### Wiring

Connect the ESP32 to the HDMI breakout board:

| ESP32-C3 SuperMini Pin | HDMI Breakout Pin | Signal |
|------------------------|-------------------|--------|
| GPIO10 | Pin 13 (CEC) | CEC data line |
| GND | Pin 17 (GND) | Ground |
| 5V (optional) | Pin 18 (5V/HPD) | Power from HDMI (if not using USB power) |

The CEC line is active-low, open-drain. The Palakis component handles the signaling -- no external pullup resistors are needed.

### Physical Placement

Each ESP32 CEC tap sits **inline** on an HDMI cable using the breakout board:

- **Output tap**: Between the matrix switch output and the TV/projector
- **Input taps**: Between each source device (Apple TV, game console, etc.) and the matrix switch input

> **Important**: The ESP32 boards are powered via USB-C. The HDMI breakout only provides the CEC signal connection, not power.

---

## ESPHome Tap Configuration

Each CEC tap runs ESPHome with the [Palakis `esphome-hdmi-cec`](https://github.com/Palakis/esphome-hdmi-cec) external component.

### Key Requirements

Every tap **must** have:

1. `promiscuous_mode: true` -- so the tap sees all CEC traffic, not just messages addressed to it
2. A **catch-all `on_message` handler** that fires a `homeassistant.event` with `source`, `destination`, `opcode`, `raw`, and `translated` fields
3. An **`api.services` entry** named `hdmi_cec_send` with `cec_destination` (int) and `cec_data` (int[]) parameters

### CEC Logical Address Assignment

Each tap needs a **unique** CEC logical address. This is critical:

> **Warning**: If your HDMI switch does NOT isolate CEC between inputs (like the Feintech), all input taps share the same physical CEC bus. Using the same logical address on multiple taps causes bus contention, address conflicts, and can trigger audio issues (repeated ARC renegotiation, buzzing, dropouts).

Choose unused addresses from the CEC address space:

| Address | CEC Device Type | Suggested Use |
|---------|----------------|---------------|
| 0x09 | Recording Device 3 | Output tap |
| 0x0B | Playback Device 3 | First input tap |
| 0x0A | Tuner 4 | Second input tap |
| 0x0E | Free Use | Third input tap |
| 0x06 | Tuner 2 | Fourth input tap |
| 0x07 | Tuner 3 | Fifth input tap |

Avoid addresses already claimed by your real devices (e.g., `0x04` = Playback Device 1, often Apple TV; `0x05` = Audio System; `0x00` = TV).

### Minimal Input Tap YAML

This is the minimum ESPHome YAML for an input-side CEC tap:

```yaml
substitutions:
  name: cec-my-input-tap
  friendly_name: CEC Tap - My Device

esphome:
  name: ${name}
  friendly_name: ${friendly_name}
  name_add_mac_suffix: false

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
  ap:
    ssid: "${name} Fallback"

captive_portal:

external_components:
  - source: github://Palakis/esphome-hdmi-cec

hdmi_cec:
  pin: GPIO10
  address: 0x0B              # Must be unique per tap — see address table above
  physical_address: 0x1110   # Source device's CEC physical address (e.g., 1.1.1.0)
  osd_name: "CEC-Tap"
  promiscuous_mode: true

  on_message:
    # Per-opcode handlers (optional but recommended for richer HA events)

    - opcode: 0x04  # Image View On (wake)
      then:
        - homeassistant.event:
            event: esphome.cec_my_input_wake
            data:
              source: !lambda return std::to_string(source);

    - opcode: 0x36  # Standby
      then:
        - homeassistant.event:
            event: esphome.cec_my_input_standby
            data:
              source: !lambda return std::to_string(source);
              destination: !lambda return std::to_string(destination);

    - opcode: 0x82  # Active Source
      then:
        - homeassistant.event:
            event: esphome.cec_my_input_active_source
            data:
              source: !lambda return std::to_string(source);

    - opcode: 0x90  # Report Power Status
      then:
        - homeassistant.event:
            event: esphome.cec_power_status
            data:
              source: !lambda return std::to_string(source);
              tap: "my_input"
              status: !lambda |-
                if (data.size() > 1) {
                  switch (data[1]) {
                    case 0x00: return std::string("on");
                    case 0x01: return std::string("standby");
                    case 0x02: return std::string("to_standby");
                    case 0x03: return std::string("to_on");
                    default:   return std::string("unknown");
                  }
                }
                return std::string("unknown");

    # Catch-all — REQUIRED for the bridge integration
    - then:
        - lambda: |-
            id(cec_raw_message).publish_state(
              hdmi_cec::Frame(source, destination, data).to_string(true)
            );
            id(cec_translated_message).publish_state(
              hdmi_cec::Frame(source, destination, data).to_string()
            );
        - homeassistant.event:
            event: esphome.hdmi_cec_my_input  # Must match catch_all_event in bridge config
            data:
              source: !lambda return std::to_string(source);
              destination: !lambda return std::to_string(destination);
              opcode: !lambda |-
                return data.size() ? std::to_string(data[0]) : std::string("0");
              raw: !lambda return hdmi_cec::Frame(source, destination, data).to_string(true);
              translated: !lambda return hdmi_cec::Frame(source, destination, data).to_string();

button:
  - platform: template
    name: "Identify"
    icon: mdi:flash-alert
    on_press:
      - light.turn_on:
          id: status_led
          effect: "Identify"
      - delay: 5s
      - light.turn_off:
          id: status_led

output:
  - platform: gpio
    pin:
      number: GPIO8
      inverted: true
    id: blue_led_output

light:
  - platform: binary
    name: "Status LED"
    id: status_led
    output: blue_led_output
    effects:
      - strobe:
          name: Identify
          colors:
            - state: true
              duration: 200ms
            - state: false
              duration: 200ms

text_sensor:
  - platform: template
    name: "HDMI CEC Raw Message"
    id: cec_raw_message
    update_interval: never

  - platform: template
    name: "HDMI CEC Translated Message"
    id: cec_translated_message
    update_interval: never

  - platform: wifi_info
    ip_address:
      name: "IP Address"
    ssid:
      name: "WiFi SSID"
```

### Output Tap Additions

The output tap (TV/projector side) benefits from additional opcode handlers for richer state tracking. Beyond the base config above, add handlers for:

- `0x7A` Report Audio Status -- volume and mute state from the audio system
- `0xC0`-`0xC4` ARC opcodes -- Audio Return Channel negotiation monitoring
- `0x44` User Control Pressed -- remote keypress visibility
- `0x80` Routing Change, `0x86` Set Stream Path -- input switching events

The output tap can also expose **audio volume and mute as ESPHome sensors** for use outside the bridge integration:

```yaml
# Add to output tap's on_message section, under opcode 0x7A handler:
    - opcode: 0x7A  # Report Audio Status
      then:
        - lambda: |-
            if (data.size() > 1) {
              int vol = data[1] & 0x7F;
              bool muted = data[1] & 0x80;
              id(audio_volume_sensor).publish_state(vol);
              id(audio_mute_sensor).publish_state(muted ? "Muted" : "Unmuted");
            }
        - homeassistant.event:
            event: esphome.cec_audio_status
            data:
              source: !lambda return std::to_string(source);
              tap: "output"
              volume: !lambda |-
                if (data.size() > 1) return std::to_string(data[1] & 0x7F);
                return std::string("0");
              muted: !lambda |-
                if (data.size() > 1) return (data[1] & 0x80) ? std::string("true") : std::string("false");
                return std::string("false");

# Add to root level of output tap YAML:
sensor:
  - platform: template
    name: "Audio Volume"
    id: audio_volume_sensor
    icon: mdi:volume-high
    unit_of_measurement: "%"
    accuracy_decimals: 0
    update_interval: never

text_sensor:
  - platform: template
    name: "Audio Mute"
    id: audio_mute_sensor
    icon: mdi:volume-mute
    update_interval: never
```

### LED Identify Feature

All taps include an **Identify button** that strobes the onboard blue LED for 5 seconds when pressed from Home Assistant. This helps locate which physical ESP32 is which when you have multiple taps:

```yaml
button:
  - platform: template
    name: "Identify"
    icon: mdi:flash-alert
    on_press:
      - light.turn_on:
          id: status_led
          effect: "Identify"
      - delay: 5s
      - light.turn_off:
          id: status_led

output:
  - platform: gpio
    pin:
      number: GPIO8       # Onboard blue LED on ESP32-C3 SuperMini
      inverted: true      # Active-low on this board
    id: blue_led_output

light:
  - platform: binary
    name: "Status LED"
    id: status_led
    output: blue_led_output
    effects:
      - strobe:
          name: Identify
          colors:
            - state: true
              duration: 200ms
            - state: false
              duration: 200ms
```

> **Note**: The ESP32-C3 SuperMini has a simple GPIO LED on GPIO8 (active-low), NOT a WS2812 addressable RGB LED. Use `platform: binary` with `inverted: true`, not `esp32_rmt_led_strip`.

### Physical Address Reference

CEC physical addresses describe the HDMI topology. Format: `A.B.C.D` (stored as 2-byte hex, e.g., `1.1.0.0` = `0x1100`).

For a Feintech-style matrix switch:

| Position | Physical Address | Hex | Notes |
|----------|-----------------|-----|-------|
| Switch output | 1.0.0.0 | 0x1000 | The switch itself |
| Input 1 (e.g., Apple TV) | 1.1.0.0 | 0x1100 | First input port |
| Input 2 (e.g., Nintendo) | 1.2.0.0 | 0x1200 | Second input port |
| Input 3 (e.g., RetroPie) | 1.3.0.0 | 0x1300 | Third input port |
| Input 4 (e.g., Turntable) | 1.4.0.0 | 0x1400 | Fourth input port |

The tap's `physical_address` in ESPHome should be one hop deeper than the device it sits beside. For example, if your Apple TV is at `1.1.0.0`, the tap inline with it uses `0x1110` (1.1.1.0).

### MQTT (Optional)

Taps can optionally publish CEC messages to MQTT for debugging or external tools:

```yaml
mqtt:
  broker: !secret mqtt_broker
  username: !secret mqtt_username
  password: !secret mqtt_password
  client_id: cec-my-tap
  discovery: false

# In the catch-all on_message handler, add:
    - mqtt.publish:
        topic: cec/my-tap/messages
        payload: !lambda |-
          return hdmi_cec::Frame(source, destination, data).to_string(true);
```

---

## ESPHome Flashing

### First Flash (USB)

1. Connect the ESP32-C3 SuperMini to your computer via USB-C
2. In the ESPHome dashboard, click **Install** > **Plug into this computer** (or use `esphome run <tap>.yaml`)
3. Select the serial port and flash

### Subsequent Flashes (OTA)

```bash
# From the ESPHome host:
esphome compile cec-my-tap.yaml
esphome upload cec-my-tap.yaml --device cec-my-tap.local
```

Use the `--device` flag to avoid the interactive upload method picker (important for scripted/remote flashing).

> **Tip**: When flashing multiple taps, compile and upload sequentially -- parallel builds can corrupt the shared PlatformIO framework cache.

---

## Prerequisites

### 1. ESPHome Service Calls

For each CEC tap device in the ESPHome integration:

1. Go to **Settings > Integrations > ESPHome**
2. Click the tap device > **Options**
3. Enable **"Allow the device to make Home Assistant service calls"**

This is required for the taps to fire `homeassistant.event` events that the bridge listens to.

### 2. HACS

Install [HACS](https://hacs.xyz/) if not already installed.

---

## Installation

1. In HACS, click the **three dots** menu > **Custom repositories**
2. Add this repository URL, category: **Integration**
3. Click **Install**
4. Restart Home Assistant

---

## Configuration

### Setup Wizard

1. Go to **Settings > Integrations > Add Integration**
2. Search for **"HDMI CEC Bridge"**
3. The integration auto-discovers ESPHome devices with CEC entities (`hdmi_cec` in the entity ID)
4. Select which taps to include in this bridge
5. Configure each tap with the following fields:

| Field | Description | Example |
|-------|-------------|---------|
| **Friendly name** | Display name for this tap | `Projector`, `Apple TV` |
| **Role** | `output` (TV/projector side) or `input` (source device side) | `output` |
| **Catch-all event name** | The `esphome.*` event this tap fires for all CEC messages | `esphome.hdmi_cec_output` |
| **ESPHome service name** | The ESPHome service to call to send CEC frames | `cec_output_tap_hdmi_cec_send` |
| **Tap logical address** | The CEC address the ESP32 tap uses (decimal) | `9` (for 0x09) |
| **Physical address** | (Input taps) Source device's CEC physical address | `1.1.0.0` |
| **Device logical address** | (Input taps, optional) Source device's CEC logical address | `4` (for Apple TV) |

### Example: 6-Tap Bridge Configuration

This example matches a Feintech matrix switch with one output and five input taps:

| Tap | Role | Event Name | Service Name | Tap Addr | Physical Addr | Device Addr |
|-----|------|-----------|--------------|----------|---------------|-------------|
| Projector | output | `esphome.hdmi_cec_output` | `cec_output_tap_hdmi_cec_send` | 9 | -- | -- |
| Apple TV | input | `esphome.hdmi_cec_atv` | `cec_atv_tap_hdmi_cec_send` | 11 | 1.1.0.0 | 4 |
| Nintendo | input | `esphome.hdmi_cec_nintendo` | `cec_nintendo_tap_hdmi_cec_send` | 10 | 1.2.0.0 | -- |
| RetroPie | input | `esphome.hdmi_cec_retropie` | `cec_retropie_tap_hdmi_cec_send` | 14 | 1.3.0.0 | 8 |
| Spare | input | `esphome.hdmi_cec_spare` | `cec_spare_tap_hdmi_cec_send` | 6 | 1.0.0.0 | -- |
| Turntable | input | `esphome.hdmi_cec_turntable` | `cec_turntable_tap_hdmi_cec_send` | 7 | 1.4.0.0 | -- |

> **Note**: The service name is derived from the ESPHome device name: hyphens become underscores, then `_hdmi_cec_send` is appended. So `cec-atv-tap` becomes `cec_atv_tap_hdmi_cec_send`.

### Options Flow

After initial setup, go to the integration's **Options** to:

- **Add** new CEC taps (re-discovers available ESPHome devices)
- **Remove** existing taps (must keep at least one input and one output)
- **Edit** tap configuration (role, label, addresses)

---

## Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.{bridge}_tv_power` | TV power state: `on` / `standby` / `to_on` / `to_standby` / `unknown` |
| `sensor.{bridge}_active_source` | Label of the currently active input |
| `sensor.{bridge}_relay_count` | Total relayed CEC frames since last reload |
| `sensor.{bridge}_{tap}_last_event` | Last CEC event on each tap (one per tap) |

### Buttons

| Entity | Action |
|--------|--------|
| `button.{bridge}_wake_tv` | Send Image View On (0x04) to TV |
| `button.{bridge}_standby_all` | Send Standby (0x36) broadcast |
| `button.{bridge}_request_tv_power` | Poll TV power status (0x8F to 0x00) |
| `button.{bridge}_request_all_power` | Poll all devices for power status (0x8F broadcast) |
| `button.{bridge}_request_audio_status` | Request audio volume/mute from audio system (0x71 to 0x05) |
| `button.{bridge}_switch_to_{input}` | Switch to a specific input via Active Source (one per input tap) |

### Number

| Entity | Description |
|--------|-------------|
| `number.{bridge}_audio_volume` | Volume slider (0-100). Sends CEC vol up/down keypresses to the audio system. Shows `muted` attribute. |

### Select

| Entity | Description |
|--------|-------------|
| `select.{bridge}_active_input` | Dropdown to choose the active input. Sends Active Source with that input's physical address. |

### Switches (Relay Rules)

| Entity | Default | Description |
|--------|---------|-------------|
| `switch.{bridge}_relay_wake_to_output` | ON | Relay wake commands (0x04/0x0D) from inputs to output |
| `switch.{bridge}_relay_standby_to_output` | ON | Relay standby (0x36) from inputs to output |
| `switch.{bridge}_relay_power_status_to_inputs` | ON | Relay power status (0x90) from output to active input |
| `switch.{bridge}_relay_power_request_to_output` | ON | Relay power requests (0x8F) from inputs to output |
| `switch.{bridge}_relay_active_source_to_output` | OFF | Relay Active Source (0x82) from inputs to output (OFF by default -- can cause loops) |

All switches use `RestoreEntity` to persist state across HA restarts.

---

## Loop Prevention

1. **Source address filtering**: If a CEC event's source address matches the tap's own logical address, it's a self-echo from a previous relay injection and is skipped
2. **Debounce**: 500ms cooldown per (opcode, relay direction) pair prevents rapid cascading
3. **Direction restriction**: Input taps only relay TO output. Output tap only relays TO the active input. No input-to-input relay.

---

## Troubleshooting

### Audio Buzzing / Dropouts After Adding Taps

If your HDMI switch does **not** isolate CEC buses between inputs (common with Feintech and similar switches), all input taps share the same physical CEC bus. Symptoms:

- Repeated `Initiate ARC` (0xC0) messages in the output tap's logs
- Audio buzzing, crackling, or brief dropouts
- ARC renegotiation loops

**Fix**: Ensure every tap on the shared bus has a **unique CEC logical address**. See the [address assignment table](#cec-logical-address-assignment) above.

### Tap Not Discovered

- Verify the tap is online in the ESPHome dashboard
- Check that the tap has `hdmi_cec` entities (look for `sensor.*_hdmi_cec_raw_message` in HA)
- Ensure the ESPHome integration has the tap connected

### Service Calls Failing

- Go to **Settings > Integrations > ESPHome > [tap device] > Options**
- Enable **"Allow the device to make Home Assistant service calls"**
- This must be done for **each** CEC tap device individually

### Identifying Physical Taps

Press the **Identify** button in HA for each tap -- the onboard blue LED will strobe for 5 seconds, making it easy to match HA entities to physical ESP32 boards.

### OTA Flash Fails

- Ensure only one `esphome compile` runs at a time -- parallel builds can corrupt the shared PlatformIO/ESP-IDF framework cache
- If builds fail after an ESP-IDF update, clear the cache: `rm -rf ~/.platformio/packages/framework-espidf` and retry
- Use `--device <hostname>.local` with `esphome upload` to skip the interactive method picker

---

## CEC Opcode Reference

| Opcode | Hex | Name | Direction |
|--------|-----|------|-----------|
| Image View On | 0x04 | Wake TV | Input > Output |
| Text View On | 0x0D | Alternate wake | Input > Output |
| Standby | 0x36 | Sleep | Input > Output |
| User Control Pressed | 0x44 | Remote keypress | Bidirectional |
| User Control Released | 0x45 | Key release | Bidirectional |
| Give Audio Status | 0x71 | Request volume/mute | Output > Audio System |
| Report Audio Status | 0x7A | Volume (0-100) + mute bit | Audio System > Output |
| Routing Change | 0x80 | Input switch notification | Output |
| Active Source | 0x82 | Declare active input | Input > Output |
| Request Active Source | 0x85 | Poll for active input | Bidirectional |
| Set Stream Path | 0x86 | Direct input to activate | Output |
| Give Device Power Status | 0x8F | Poll power state | Bidirectional |
| Report Power Status | 0x90 | Power state response | Output > Input |
| Inactive Source | 0x9D | Declare inactive | Input |
| Initiate ARC | 0xC0 | Start audio return channel | TV > Audio System |

### CEC Logical Addresses

| Address | Hex | Device Type |
|---------|-----|-------------|
| 0 | 0x00 | TV |
| 1 | 0x01 | Recording Device 1 |
| 3 | 0x03 | Tuner 1 |
| 4 | 0x04 | Playback Device 1 (often Apple TV) |
| 5 | 0x05 | Audio System |
| 6 | 0x06 | Tuner 2 |
| 7 | 0x07 | Tuner 3 |
| 8 | 0x08 | Playback Device 2 |
| 9 | 0x09 | Recording Device 3 |
| 10 | 0x0A | Tuner 4 |
| 11 | 0x0B | Playback Device 3 |
| 14 | 0x0E | Free Use |
| 15 | 0x0F | Broadcast |

---

## License

MIT
