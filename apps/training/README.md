# Bird Training

Detector and classifier training pipeline for the Bird Pokedex.

## Status

Stub only. Requires `make sync-training` and GPU/CPU hardware.

## Planned pipeline

1. Load `ImageManifestRecord` dataset from `data/manifests/`
2. Train detector (YOLO-family or DETR) — `train_detector.py`
3. Train classifier (timm EfficientNet or ViT) — `train_classifier.py`
4. Export to ONNX — `export_onnx.py`
5. Evaluate calibration — `evaluate.py`
