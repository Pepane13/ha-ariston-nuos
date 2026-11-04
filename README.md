# Ariston Nuos for Home Assistant

Custom integration for **Ariston Nuos heat pump water heaters** (Ariston NET cloud, "Velis" SLP plants, `wheType` 4).

It was written because the Home Assistant core `ariston` integration cannot select the **GREEN** mode on these heaters: the cloud accepts the command and ignores it. The mode change request must carry the current mode as `old`:

```json
POST velis/slpPlantData/<gateway>/operativeMode
{"new": 0, "old": 1}
```

python-ariston-api 0.19.9 sends `{"new": 0}` only. A missing `old` most likely reads as 0, which is GREEN, so the cloud sees no change. This integration always sends an `old` value different from the new one.

## Features

| Entity | What it does |
|---|---|
| `water_heater` | Water temperature, comfort set point, operation mode (GREEN, COMFORT, FAST, IMEMORY — same names as the core integration), on/off |
| `select` Mode | Same operation mode, for dashboards |
| `switch` Power, Boost | Live commands |
| `switch` Anti-legionella, Preheating | Plant settings |
| `number` Reduced temperature, Green maximum, minimum / maximum set point, heating rate (disabled by default) | Set points and settings |
| `binary_sensor` Heat pump | Heat pump running |
| `sensor` Water temperature, requested temperature, current mode, heat pump / resistor energy of the last day | Readings |
| `button` Refresh | Reads state, settings and energy again |

Every command is shown at once, then read back from the cloud 20 seconds later, and fires an `ariston_nuos_command` event (command, new and old value) that automations or the logbook can use.

Polling: every 2 minutes by default (options: 1–30 min); settings every 6 h; energy every hour. Requests are serialised; after an HTTP 429 the client pauses for 15 minutes.

## Installation

1. HACS → Integrations → ⋮ → Custom repositories → `https://github.com/Pepane13/ha-ariston-nuos` (Integration).
2. Install **Ariston Nuos**, restart Home Assistant.
3. Settings → Devices & services → Add integration → **Ariston Nuos**, sign in with the Ariston NET account. The credentials are stored only in Home Assistant.

It can run next to the core `ariston` integration, but both poll the same cloud: disable one of them once the other is validated.

## Tests

```bash
pip install pytest-homeassistant-custom-component
pytest
```

## Credits

Endpoints follow the reverse-engineered [python-ariston-api](https://github.com/fustom/python-ariston-api). The `old` fix matches fustom/python-ariston-api PR #174.
