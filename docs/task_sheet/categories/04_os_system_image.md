# 4 — Custom OS / system image

**Home:** `os/` (new). **Owns:** image build, provisioning, systemd, Wi-Fi AP, FTP ingest, storage.
**Assembles:** cat 3 app + cat 5 firmware devices. **Verified by:** cat 7.
Definition: [WORK_CATEGORIES.md §4](../../WORK_CATEGORIES.md#4-custom-os--system-image) ·
[os/README.md](../../../os/README.md).

## Base image
- [ ] Choose target: Raspberry Pi 5 (16GB) + AI HAT+ (per legacy §5).
- [ ] Pick reproducible build path (pi-gen / rpi-image-gen / packer) → `os/image/`.
- [ ] Pin OS + package versions; document rebuild steps.
- [ ] NVMe boot + storage layout; mount `/opt/birddex`.
- [ ] Auto-login + kiosk launch of the UI → `os/kiosk/`.

## Services (`os/systemd/`)
- [ ] `birddex-ingest.service` — watch FTP/USB/camera folders.
- [ ] `birddex-infer.service` — detect/crop/classify/rerank/log.
- [ ] `birddex-ui.service` — touchscreen/web UI.
- [ ] `birddex-sensors.service` — GPS/pressure/temp/humidity (cat 6).
- [ ] `birddex-backup.service` — export sightings + model metadata to USB/NVMe.
- [ ] Restart-on-failure + ordering (`After=`/`Requires=`).

## Networking (`os/network/`)
- [ ] hostapd + dnsmasq — local Wi-Fi AP for A7R V.
- [ ] vsftpd — FTP ingest folder for Sony JPEGs.
- [ ] Firewall: offline by default, no outbound required after setup.

## Provisioning (`os/provisioning/`)
- [ ] `first-boot.sh` — hostname, services, storage, network.
- [ ] `install_device.sh` — stage app + `models/exports/*` + `configs/{device,inference}/` into `/opt/birddex/`.
- [ ] udev rules for MCU/GPS serial ports (with cat 5/6).
- [ ] Consider read-only root / overlay for power-loss safety.

## Interfaces / acceptance
- [ ] systemd units resolve `/opt/birddex` paths that cat 3 expects.
- [ ] Device boots straight into UI, creates its Wi-Fi AP, accepts A7R V JPEGs — no terminal.
- [ ] Flashable image handed to cat 7 for smoke test.
