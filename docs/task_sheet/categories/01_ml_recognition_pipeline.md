# 1 — ML bird recognition pipeline

**Homes:** `apps/training/`, `packages/bird_ml/`, `configs/training/`, `models/`.
**Owns:** detector + classifier training, calibration, evaluation, ONNX export.
**Consumes:** manifest/splits (cat 2). **Produces:** `models/exports/*` for cat 3.
Definition: [WORK_CATEGORIES.md §1](../../WORK_CATEGORIES.md#1-ml-bird-recognition-pipeline).

## Data / dependency preconditions
- [ ] `training` + `vision` + `inference` uv groups sync cleanly (`make sync-*`).
- [~] `data/splits/{train,val,test}.csv` exist (from cat 2 dry-run).
- [ ] Real labelled media retrieved for prototype-ROI species (cat 2 opt-in step).

## Classifier
- [~] `bird_training/dataset.py` — manifest → Dataset (skeleton).
- [~] `bird_training/train_classifier.py` — fails fast without deps (skeleton).
- [ ] Wire `configs/training/classifier.yaml` (backbone, input size, LR, epochs).
- [ ] Baseline: MobileNetV3-Large or EfficientNetV2-B0/B1 transfer-learned.
- [ ] Class imbalance handling (weighted loss / sampler) for the ROI tiers.
- [ ] Save checkpoints to `models/checkpoints/`.

## Detector
- [~] `bird_training/train_detector.py` (skeleton).
- [ ] Choose lightweight bird/not-bird detector (YOLO-family / RT-DETR).
- [ ] Wire `configs/training/detector.yaml`.
- [ ] Validate crops keep beak/tail/wings (feeds cat 3 cropper).

## Augmentation, calibration, metrics (bird_ml)
- [ ] `configs/training/augmentation.yaml` tuned for field-like images.
- [~] `bird_ml/calibration.py` — temperature scaling on held-out split.
- [~] `bird_ml/metrics.py` — top-1/top-5, per-class, confusion, ECE, unknown-rejection.
- [~] `bird_ml/labels.py` — LabelMap is the class↔id contract with cat 3.

## Evaluation
- [~] `bird_training/evaluate.py` (skeleton) → reports in `data/reports/`.
- [ ] Confusion matrix over similar-species clusters (honeyeaters, robins, thornbills…).
- [ ] Eval on clean / field-like / negative test sets.

## Export (contract with cat 3)
- [~] `bird_training/export_onnx.py` — fails fast without deps (skeleton).
- [ ] Export `detector.onnx`, `classifier.onnx`, `label_map.json` to `models/exports/`.
- [ ] Record fixed input/output signature + preprocessing (documented for cat 3).
- [ ] (Later) quantize / Hailo `.hef` into `models/quantized/`, keep ONNX fallback.

## Acceptance
- [ ] Useful top-5 for common prototype-ROI birds; honest "unsure" below threshold.
- [ ] Every prediction can log model version + confidence (with cat 3).
