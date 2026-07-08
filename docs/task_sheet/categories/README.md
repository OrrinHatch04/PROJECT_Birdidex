# Category task sheets

One checklist per work category. See [../../WORK_CATEGORIES.md](../../WORK_CATEGORIES.md) for the
definitions (purpose, boundaries, files, I/O, dependencies, interfaces) and
[../SEQ_BirdDex_Task_Sheet.md](../SEQ_BirdDex_Task_Sheet.md) for the original end-to-end plan.

Prototype ROI = three SEQ corridors (Lamington/Springbrook, Bribie→Nudgee→Beerburrum,
Noosa→Rainbow Beach→K'gari). Config: `configs/roi/prototype_roi.{geojson,yaml}`.

| # | Category | Checklist | Status |
|---|----------|-----------|--------|
| 1 | ML bird recognition pipeline | [01](01_ml_recognition_pipeline.md) | Skeletons, no weights |
| 2 | Dataset acquisition, filtering & ROI validation | [02](02_dataset_acquisition_roi.md) | Offline dry-run works |
| 3 | Offline application / UI | [03](03_offline_app_ui.md) | Mock inference + UI skeleton |
| 4 | Custom OS / system image | [04](04_os_system_image.md) | Scaffold only |
| 5 | Electronics & microcontroller firmware | [05](05_firmware.md) | Scaffold only |
| 6 | Camera / sensor integration | [06](06_camera_sensor_integration.md) | Protocols only |
| 7 | Deployment, testing & field validation | [07](07_deployment_testing_field.md) | Tests + verify pass |
| 8 | Shared configs, schemas, data contracts & docs | [08](08_shared_contracts_docs.md) | Established |

Convention: `[ ]` todo · `[~]` in progress / stub exists · `[x]` done.
