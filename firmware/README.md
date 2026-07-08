# firmware/ — Electronics & microcontroller firmware

**Work category 5.** Firmware and low-level electronics that run *off* the main Raspberry Pi:
sensor microcontrollers, physical-button/rotary input, power management, and status LEDs.
The Pi-side Python that *consumes* these signals lives in `packages/bird_device/` and
`apps/inference/` (work category 6 — camera/sensor integration); this folder owns only what
runs on the MCU and the wiring it assumes.

## Boundary

- **In scope:** MCU firmware source (e.g. RP2040 / ESP32), serial/I²C protocol definitions the
  MCU speaks, wiring diagrams, bill of materials, flashing scripts, power-rail design.
- **Out of scope:** Anything that runs on the Pi under Python. If it `import`s `bird_*`, it
  belongs in a package/app, not here. The **shared wire protocol** (message framing, field
  names, units) is a data contract — define it once under `firmware/protocol/` and have the
  Pi-side `bird_device` driver read the same spec.

## Suggested layout

```
firmware/
├── sensor_mcu/          # GPS + BME280/BME680 aggregator firmware (serial/I2C -> Pi)
├── input_mcu/           # buttons, rotary encoder, shutdown button, status LEDs
├── power/               # battery gauge / BMS notes, power-rail schematic, load budget
├── protocol/            # SHARED wire protocol (framing, fields, units) — the data contract
├── hardware/            # KiCad/schematic, wiring diagrams, BOM.csv
└── tools/               # flashing / serial-monitor helper scripts
```

## Interfaces with other categories

| Direction | With | Contract |
|-----------|------|----------|
| out | Camera/sensor integration (`bird_device`) | serial/I²C frames defined in `firmware/protocol/` |
| in | Custom OS image (`os/`) | udev rules + device tree for the MCU serial port |
| in | Shared configs (`configs/device/`) | pin map / baud / sensor addresses |

Task checklist: [docs/task_sheet/categories/05_firmware.md](../docs/task_sheet/categories/05_firmware.md)
