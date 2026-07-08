"""Classifier training entry point.

Runnable with the ``training`` dependency group installed (torch + timm). Without those
deps every training call fails fast with a clear install message rather than an obscure
ImportError deep in the stack — the dependency boundary is explicit.

Label-map construction and config loading are pure (no torch) so the dataset contract can
be built and tested on any machine; only the actual training loop needs the heavy stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bird_core.schemas import DatasetSplit
from bird_data.csvio import load_manifest_csv
from bird_ml.labels import LabelMap

INSTALL_HINT = "install the 'training' group:  uv sync --group training"


def build_label_map_from_manifest(manifest_path: Path) -> LabelMap:
    """Build a deterministic label map from the scientific names in a manifest CSV."""
    records = load_manifest_csv(manifest_path)
    names = [r.scientific_name for r in records if r.scientific_name.strip()]
    if not names:
        raise ValueError(f"no labelled records in {manifest_path}")
    return LabelMap.from_species(names)


def compute_class_weights(manifest_path: Path, label_map: LabelMap) -> list[float]:
    """Inverse-frequency class weights (for a weighted loss / sampler)."""
    records = load_manifest_csv(manifest_path)
    counts = [0] * len(label_map)
    for r in records:
        try:
            counts[int(label_map.to_index(r.scientific_name))] += 1  # type: ignore[arg-type]
        except KeyError:
            continue
    total = sum(counts) or 1
    return [total / (len(label_map) * c) if c else 0.0 for c in counts]


@dataclass
class TrainConfig:
    backbone: str = "efficientnet_b0"
    pretrained: bool = True
    image_size: int = 224
    epochs: int = 50
    batch_size: int = 32
    learning_rate: float = 1e-4
    weight_decay: float = 1e-4

    @classmethod
    def from_yaml(cls, path: Path) -> TrainConfig:
        import yaml

        raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        model = raw.get("model", {})
        training = raw.get("training", {})
        data = raw.get("data", {})
        return cls(
            backbone=model.get("backbone", cls.backbone),
            pretrained=model.get("pretrained", cls.pretrained),
            image_size=int(data.get("image_size", cls.image_size)),
            epochs=int(training.get("epochs", cls.epochs)),
            batch_size=int(training.get("batch_size", cls.batch_size)),
            learning_rate=float(training.get("learning_rate", cls.learning_rate)),
            weight_decay=float(training.get("weight_decay", cls.weight_decay)),
        )


def _require_torch() -> tuple[Any, Any]:
    try:
        import timm  # noqa: F401
        import torch
    except ImportError as exc:  # pragma: no cover - exercised only without training deps
        raise ImportError(f"torch and timm are required to train — {INSTALL_HINT}") from exc
    return torch, timm


def train(manifest_path: Path, config_path: Path, output_dir: Path) -> Path:
    """Train a species classifier and save a checkpoint + label map.

    Returns the checkpoint path. Requires the ``training`` dependency group; the label
    map and per-class weights are computed first (pure) so a misconfigured dataset fails
    before the heavy stack is touched.
    """
    label_map = build_label_map_from_manifest(manifest_path)
    class_weights = compute_class_weights(manifest_path, label_map)
    config = TrainConfig.from_yaml(config_path)

    torch, timm = _require_torch()  # pragma: no cover - requires training deps

    from bird_ml.metrics import confusion_matrix, per_class_prf, top_k_accuracy, weighted_f1

    from bird_training.dataset import ManifestImageDataset

    output_dir.mkdir(parents=True, exist_ok=True)
    label_map.to_json(output_dir / "label_map.json")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = timm.create_model(
        config.backbone, pretrained=config.pretrained, num_classes=len(label_map)
    ).to(device)

    train_ds = ManifestImageDataset(manifest_path, label_map, split=DatasetSplit.train,
                                    image_size=config.image_size, train=True)
    val_ds = ManifestImageDataset(manifest_path, label_map, split=DatasetSplit.val,
                                  image_size=config.image_size, train=False)

    weight_t = torch.tensor(class_weights, dtype=torch.float32, device=device)
    criterion = torch.nn.CrossEntropyLoss(weight=weight_t)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    train_loader = torch.utils.data.DataLoader(train_ds, batch_size=config.batch_size, shuffle=True)
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=config.batch_size)

    for _epoch in range(config.epochs):
        model.train()
        for images, targets in train_loader:
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), targets)
            loss.backward()
            optimizer.step()

    # Validation metrics (top-1/top-5, weighted F1, per-class, confusion matrix).
    import numpy as np

    model.eval()
    all_scores: list[np.ndarray] = []
    all_labels: list[int] = []
    with torch.no_grad():
        for images, targets in val_loader:
            logits = model(images.to(device))
            all_scores.append(logits.cpu().numpy())
            all_labels.extend(int(t) for t in targets)
    if all_scores:
        scores = np.concatenate(all_scores, axis=0)
        labels = np.array(all_labels)
        preds = scores.argmax(axis=1)
        metrics = {
            "top1": top_k_accuracy(scores, labels, k=1),
            "top5": top_k_accuracy(scores, labels, k=5),
            "weighted_f1": weighted_f1(labels, preds, len(label_map)),
            "per_class": per_class_prf(labels, preds, len(label_map)),
        }
        np.savetxt(output_dir / "confusion_matrix.csv",
                   confusion_matrix(labels, preds, len(label_map)), fmt="%d", delimiter=",")
        import json

        (output_dir / "val_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))

    # TODO: post-hoc temperature-scaling calibration on the val split (see bird_ml.calibration).
    ckpt_path = output_dir / "classifier.pt"
    torch.save({"state_dict": model.state_dict(), "backbone": config.backbone,
                "num_classes": len(label_map)}, ckpt_path)
    return ckpt_path
