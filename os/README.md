# os/ — Custom OS & system image

**Work category 4.** Everything that turns a blank Raspberry Pi into a BirdDex appliance that
boots straight into the UI with no terminal: image build, first-boot provisioning, systemd
services, Wi-Fi access point, and FTP ingest. This owns *how the device is assembled and
boots*; the application code it launches lives in `apps/` and `packages/`.

## Boundary

- **In scope:** image-build recipe, `systemd` unit files, first-boot/provisioning scripts,
  network (Wi-Fi AP + FTP) config, kiosk/auto-login, storage layout (NVMe mount), OS-level
  hardening and read-only-root considerations.
- **Out of scope:** Python application logic (that is inference/UI), and MCU firmware (that is
  `firmware/`). This folder *installs and wires up* those, it does not reimplement them.

## Suggested layout

```
os/
├── image/               # image-build recipe (pi-gen / rpi-image-gen / packer) + pinned versions
├── systemd/             # birddex-ingest / -infer / -ui / -sensors / -backup .service units
├── provisioning/        # first-boot.sh, install_device.sh, enable-services, apply-config
├── network/             # hostapd + dnsmasq (Wi-Fi AP), vsftpd (Sony FTP ingest) configs
├── kiosk/               # auto-login + browser/UI kiosk launch
└── overlays/            # /opt/birddex file layout staged into the image
```

## Target on-device layout (`/opt/birddex/`)

Mirrors §8.2 of the legacy task sheet: `app/ models/ data/ media/ logs/ exports/ config/`.

## Interfaces with other categories

| Direction | With | Contract |
|-----------|------|----------|
| launches | Offline app / UI (`apps/inference`, `apps/cyberdeck_ui`) | systemd units + `/opt/birddex` paths |
| consumes | ML pipeline (`models/exports/`) | ONNX/HEF + `label_map.json` staged into the image |
| consumes | Shared configs (`configs/device/`, `configs/inference/`) | copied to `/opt/birddex/config/` |
| enables | Firmware (`firmware/`) | udev rules for MCU/GPS serial ports |
| verified by | Deployment & field validation (`scripts/deployment/`) | flashable image + smoke test |

Task checklist: [docs/task_sheet/categories/04_os_system_image.md](../docs/task_sheet/categories/04_os_system_image.md)
