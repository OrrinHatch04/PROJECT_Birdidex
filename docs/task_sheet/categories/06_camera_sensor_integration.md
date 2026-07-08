# 6 — Camera / sensor integration

**Homes:** `packages/bird_device/`, `apps/inference/camera.py`, `configs/device/`.
**Owns:** Pi-side camera + sensor abstraction. **Consumes:** firmware frames (cat 5).
**Feeds:** inference pipeline (cat 3). **Launched by:** cat 4.
Definition: [WORK_CATEGORIES.md §6](../../WORK_CATEGORIES.md#6-camera--sensor-integration).

## Camera abstraction (`bird_device.camera_base` + `bird_inference.camera`)
- [~] `camera_base.py` — `CameraProtocol` (the contract cat 3 depends on).
- [ ] Pi Camera Module 3 / HQ capture driver.
- [ ] Sony A7R V FTP-JPEG ingest: watch folder, EXIF extract (timestamp, model, focal length, GPS).
- [ ] USB/card copy fallback path.
- [ ] Normalize frames (resize/RGB) before handing to detector.
- [ ] JPEG-only for field (RAW/ARW archived, not classified — per legacy §4.4).

## Sensors / telemetry (`bird_device.telemetry`, `.battery`)
- [~] `telemetry.py` — GPS/pressure/temp/humidity abstraction.
- [~] `battery.py` — battery/voltage telemetry.
- [ ] Parse cat-5 wire protocol frames (or read Pi-direct GPS/BME if no MCU).
- [ ] Assemble per-observation snapshot: lat/lon/alt/temp/humidity/pressure/light/battery.
- [ ] GPS-lock + sensor-health status for the UI (cat 3) and LEDs (cat 5).

## Config
- [~] `configs/device/cyberdeck.yaml` — camera + sensor + ingest config (single source of truth).
- [ ] Keep pin map / addresses aligned with `firmware/hardware/` (no duplication).

## Interfaces / acceptance
- [ ] `CameraProtocol` implemented for both Pi camera and A7R V ingest; swappable/mockable.
- [ ] Sensor snapshot fields match cat-3 observation log schema (owned by cat 8).
- [ ] Real A7R V JPEG lands in ingest folder → frame + sensor snapshot reach cat 3.
