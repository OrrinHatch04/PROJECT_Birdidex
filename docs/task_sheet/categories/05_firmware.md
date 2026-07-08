# 5 — Electronics & microcontroller firmware

**Home:** `firmware/` (new). **Owns:** MCU firmware, wire protocol, hardware design.
**Pi-side consumer:** `bird_device` (cat 6). **Wired into image by:** cat 4.
Definition: [WORK_CATEGORIES.md §5](../../WORK_CATEGORIES.md#5-electronics--microcontroller-firmware) ·
[firmware/README.md](../../../firmware/README.md).

## Decide scope (MVP may be MCU-less)
- [ ] Decide: dedicated sensor MCU, or GPS/BME straight to Pi via USB/I²C?
      (A Pi-direct path lets cat 6 proceed without firmware for the September MVP.)
- [ ] If MCU used, choose board (RP2040 / ESP32) and record in `firmware/hardware/BOM.csv`.

## Shared wire protocol (data contract — define once)
- [ ] `firmware/protocol/` — message framing, field names, units, versioning.
- [ ] Same spec read by MCU firmware and by `bird_device` (no duplicated definitions).

## Sensor MCU (`firmware/sensor_mcu/`)
- [ ] Read GPS (u-blox) + BME280/BME680 (temp/humidity/pressure).
- [ ] Emit framed telemetry over serial/I²C at fixed cadence.
- [ ] Timestamp fallback (RTC) when GPS lock absent.

## Input MCU / controls (`firmware/input_mcu/`)
- [ ] Debounced buttons: Capture, Process-latest, Confirm, Unsure, Back.
- [ ] Safe-shutdown button → signal Pi (with cat 4).
- [ ] Status LEDs: power / GPS lock / processing.

## Power (`firmware/power/`)
- [ ] Battery pack + BMS selection; log battery voltage if custom pack.
- [ ] Power-rail schematic + load budget (screen is usually dominant drain).

## Hardware (`firmware/hardware/`)
- [ ] Wiring diagram + pin map (mirror `configs/device/cyberdeck.yaml`).
- [ ] BOM with links.

## Interfaces / acceptance
- [ ] Framed telemetry parses in `bird_device` (cat 6) round-trip test.
- [ ] Buttons drive cat-3 UI actions; shutdown button triggers graceful cat-4 shutdown.
