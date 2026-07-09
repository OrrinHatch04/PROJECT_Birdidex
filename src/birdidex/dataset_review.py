"""Deterministic bird-photo dataset review pipeline.

This module audits candidate bird images *before* they are allowed into
model-training splits. It never deletes or moves originals; it only reads the
image pool and writes machine-readable reports so a human (or a later supervised
classifier) can decide what to keep.

The review gate answers, per image:

* Does the file open at all? (missing / empty / corrupt -> ``rejected``)
* Is a bird-like subject detected by a COCO YOLO detector?
* Is the subject large enough in frame?
* Is the bird crop sharp enough (Laplacian variance)?
* Does the crop have usable contrast and exposure?
* Are there scope / vignette / dark-border artefacts?

Everything heavy (the detector, optional IQA / DINOv2 feature models) is imported
lazily and fails gracefully, so importing this module and running the base
deterministic review never requires ``ultralytics``/``pyiqa``/``timm`` to be present.

Note: there is no pretrained "bird-photo usability" model. This pipeline produces
*features and rule-based decisions* that can later train a supervised
accept/quarantine/reject classifier.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
from PIL import Image, ImageOps

from birdidex.images import image_records_path
from birdidex.paths import data_dir, images_dir, repo_root, reports_dir

Decision = Literal["accepted", "quarantine", "rejected"]

# --------------------------------------------------------------------------- #
# Suffix policy: the review defaults to raster files only. RAW is tracked
# separately and excluded until a conversion step exists.
# --------------------------------------------------------------------------- #
RASTER_SUFFIXES: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".webp"})
RAW_SUFFIXES: frozenset[str] = frozenset(
    {".arw", ".arq", ".srf", ".sr2", ".nef", ".nrw", ".cr3", ".cr2", ".crw"}
)
# Default image set for review == raster only. RAW stays out of scope for now.
IMAGE_SUFFIXES: frozenset[str] = RASTER_SUFFIXES

METADATA_PATH_KEYS: tuple[str, ...] = (
    "local_path",
    "image_path",
    "path",
    "processed_path",
    "raw_path",
    "file_path",
)
LABEL_KEYS: tuple[str, ...] = ("label", "common_name", "species", "class_name")
OBSERVATION_ID_KEYS: tuple[str, ...] = (
    "provider_observation_id",
    "observation_id",
    "id",
)

DEFAULT_DETECTOR_MODEL = "yolo11s.pt"

REPORT_JSONL = "dataset_quality_review_dry_run.jsonl"
REPORT_CSV = "dataset_quality_review_dry_run.csv"
REPORT_CONTACT_SHEET = "dataset_quality_contact_sheet_dry_run.png"


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class QualityConfig:
    """Thresholds for the deterministic review gate.

    Every rejected/quarantined image gets a machine-readable reason, so these
    numbers can be recalibrated against a labelled sample later.
    """

    # Detector
    detector_model_name: str = DEFAULT_DETECTOR_MODEL
    detector_conf: float = 0.25
    detector_rescue_conf: float = 0.08
    detector_device: str | None = None
    bird_class_name: str = "bird"
    detector_batch_size: int = 16
    detector_chunk_size: int = 128
    bbox_pad_frac: float = 0.20
    edge_touch_frac: float = 0.025
    obstruction_conf_threshold: float = 0.35

    # Subject size (fraction of the whole frame covered by the bbox)
    min_bbox_area_frac_classifier: float = 0.06
    min_bbox_area_frac_detector: float = 0.02
    max_bbox_area_frac: float = 0.95

    # Crop quality
    min_laplacian_var: float = 60.0
    min_crop_contrast_std: float = 18.0
    max_underexposed_frac: float = 0.25
    max_overexposed_frac: float = 0.15

    # Artefacts
    max_dark_border_frac: float = 0.30

    # Multi-subject handling
    max_bird_detections_for_classifier: int = 1

    # File sanity
    min_image_edge: int = 128

    # Decision policy: soft failures become "quarantine" rather than "rejected".
    quarantine_instead_of_reject: bool = True

    @classmethod
    def from_env(cls) -> QualityConfig:
        """Build a config, honouring the detector env overrides."""
        return cls(
            detector_model_name=os.environ.get("BIRDIDEX_DETECTOR_MODEL", DEFAULT_DETECTOR_MODEL),
            detector_device=detector_device_from_env(),
            detector_batch_size=_env_int("BIRDIDEX_DETECTOR_BATCH_SIZE", 16),
            detector_chunk_size=_env_int("BIRDIDEX_DETECTOR_CHUNK_SIZE", 128),
        )


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def torch_device_summary() -> dict[str, Any]:
    """Return a small PyTorch accelerator summary for CLI/notebook diagnostics.

    PyTorch exposes AMD ROCm devices through the ``torch.cuda`` API. On this
    workstation the visible ROCm device may be reported with a generic name, so
    total memory and GCN architecture are included to make the selected GPU
    auditable.
    """
    env = {
        "BIRDIDEX_DETECTOR_DEVICE": os.environ.get("BIRDIDEX_DETECTOR_DEVICE"),
        "HIP_VISIBLE_DEVICES": os.environ.get("HIP_VISIBLE_DEVICES"),
        "ROCR_VISIBLE_DEVICES": os.environ.get("ROCR_VISIBLE_DEVICES"),
        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "HSA_OVERRIDE_GFX_VERSION": os.environ.get("HSA_OVERRIDE_GFX_VERSION"),
    }
    summary: dict[str, Any] = {
        "torch_available": False,
        "backend": "unavailable",
        "cuda_available": False,
        "device_count": 0,
        "devices": [],
        "env": env,
    }
    try:
        import torch  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001 - diagnostics should not break review
        summary["error"] = f"{type(exc).__name__}: {exc}"
        return summary

    summary["torch_available"] = True
    summary["torch_version"] = getattr(torch, "__version__", None)
    summary["cuda_version"] = getattr(torch.version, "cuda", None)
    summary["hip_version"] = getattr(torch.version, "hip", None)
    summary["backend"] = "rocm" if summary["hip_version"] else "cuda"

    cuda_available = bool(torch.cuda.is_available())
    summary["cuda_available"] = cuda_available
    if not cuda_available:
        summary["backend"] = "cpu"
        return summary

    count = int(torch.cuda.device_count())
    summary["device_count"] = count
    devices: list[dict[str, Any]] = []
    for index in range(count):
        try:
            props = torch.cuda.get_device_properties(index)
            devices.append(
                {
                    "index": index,
                    "name": torch.cuda.get_device_name(index),
                    "total_memory_gb": round(float(props.total_memory) / 1024**3, 2),
                    "gcn_arch_name": getattr(props, "gcnArchName", None),
                }
            )
        except Exception as exc:  # noqa: BLE001
            devices.append({"index": index, "error": f"{type(exc).__name__}: {exc}"})
    summary["devices"] = devices
    return summary


def auto_detector_device() -> str | None:
    """Choose a detector device when the user did not set one explicitly."""
    summary = torch_device_summary()
    if summary.get("cuda_available") and int(summary.get("device_count") or 0) > 0:
        return "0"
    return None


def detector_device_from_env() -> str | None:
    raw = os.environ.get("BIRDIDEX_DETECTOR_DEVICE")
    if raw is None:
        return auto_detector_device()
    value = raw.strip()
    if not value or value.lower() == "auto":
        return auto_detector_device()
    return value


@dataclass(frozen=True)
class DryRunConfig:
    """Review behaviour, driven by ``BIRDIDEX_*`` environment vars."""

    enabled: bool = True
    all_classes: bool = False
    review_class: str | None = None
    max_images: int = 12
    detector_model: str = DEFAULT_DETECTOR_MODEL
    copy_images: bool = False
    reason_subdirs: bool = True
    enable_iqa: bool = False
    enable_dinov2: bool = False

    @classmethod
    def from_env(cls) -> DryRunConfig:
        dry_run = _env_flag("BIRDIDEX_DRY_RUN", True)
        all_classes = _env_flag("BIRDIDEX_REVIEW_ALL_CLASSES", False) or not dry_run
        review_class = os.environ.get("BIRDIDEX_DRY_RUN_CLASS") or None
        return cls(
            enabled=dry_run,
            all_classes=all_classes,
            review_class=review_class,
            max_images=_env_int("BIRDIDEX_MAX_REVIEW_IMAGES", 12),
            detector_model=os.environ.get("BIRDIDEX_DETECTOR_MODEL", DEFAULT_DETECTOR_MODEL),
            copy_images=_env_flag("BIRDIDEX_COPY_REVIEW_IMAGES", all_classes),
            reason_subdirs=_env_flag("BIRDIDEX_REVIEW_REASON_SUBDIRS", True),
            enable_iqa=_env_flag("BIRDIDEX_ENABLE_IQA", False),
            enable_dinov2=_env_flag("BIRDIDEX_ENABLE_DINOV2", False),
        )


# --------------------------------------------------------------------------- #
# Review record
# --------------------------------------------------------------------------- #
@dataclass
class ImageQualityReview:
    image_path: str
    claimed_label: str | None
    class_folder: str | None
    source_stage: str | None
    provider: str | None
    provider_observation_id: str | None
    decision: Decision
    reasons: list[str]
    primary_reason: str | None = None

    width: int | None = None
    height: int | None = None

    detector_conf: float | None = None
    detector_rescue_used: bool = False
    bird_detections: int = 0
    detector_bbox_xyxy: list[float] | None = None
    bbox_xyxy: list[float] | None = None
    detector_bbox_area_frac: float | None = None
    bbox_area_frac: float | None = None

    crop_laplacian_var: float | None = None
    crop_contrast_std: float | None = None
    crop_underexposed_frac: float | None = None
    crop_overexposed_frac: float | None = None
    dark_border_frac: float | None = None

    # Optional feature hooks (never populated unless explicitly enabled).
    iqa_scores: dict[str, float] | None = None
    dinov2_dim: int | None = None

    notes: str | None = None


# --------------------------------------------------------------------------- #
# JSONL / path helpers
# --------------------------------------------------------------------------- #
def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of dicts, tolerating blank/bad lines."""
    if not path.is_file():
        raise FileNotFoundError(f"The required JSONL path does not exist: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"[warn] bad JSONL line {line_no} in {path}: {exc}")
    return rows


def has_image_suffix(
    path_like: str | os.PathLike[str], suffixes: frozenset[str] = IMAGE_SUFFIXES
) -> bool:
    """Fast, case-insensitive suffix check that only lowercases the extension."""
    _, ext = os.path.splitext(os.fspath(path_like))
    return ext.lower() in suffixes


def iter_image_files_fast(
    roots: Iterable[Path], suffixes: frozenset[str] = IMAGE_SUFFIXES
) -> Iterator[Path]:
    """Recursively yield image files under ``roots`` using an ``os.scandir`` stack.

    Avoids ``pathlib.rglob`` overhead and never follows symlinks.
    """
    stack: list[str] = [os.fspath(root) for root in roots if Path(root).exists()]

    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        if has_image_suffix(entry.name, suffixes):
                            yield Path(entry.path)
                    except OSError:
                        # Broken entry / deleted during scan / permission issue.
                        continue
        except OSError:
            # Missing or inaccessible directory.
            continue


def safe_relpath(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` when possible, else an absolute string.

    Paths outside the repo must not crash the pipeline.
    """
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except (ValueError, OSError):
        return str(path.resolve()) if path.is_absolute() else os.path.abspath(path)


def _default_roots() -> tuple[Path, ...]:
    root = repo_root()
    data_root = data_dir()
    images_root = images_dir()
    return (
        root,
        data_root,
        images_root,
        data_root / "raw",
        data_root / "processed",
        images_root / "raw",
        images_root / "processed",
    )


def resolve_image_path(
    record: dict[str, Any],
    *,
    roots: Sequence[Path] | None = None,
    suffixes: frozenset[str] = IMAGE_SUFFIXES,
) -> Path | None:
    """Resolve an on-disk image path from a metadata record.

    Tries every known path key (``local_path``, ``image_path``, ``path``,
    ``processed_path``, ``raw_path``, ``file_path``). For each value it accepts an
    absolute path, or a path relative to any of the search roots (repo root,
    data root, images root, raw root, processed root).
    """
    search_roots = tuple(roots) if roots is not None else _default_roots()

    for key in METADATA_PATH_KEYS:
        value = record.get(key)
        if not value:
            continue
        raw = Path(str(value))

        candidates: list[Path] = []
        if raw.is_absolute():
            candidates.append(raw)
        else:
            candidates.extend(base / raw for base in search_roots)

        for candidate in candidates:
            if candidate.is_file() and candidate.suffix.lower() in suffixes:
                return candidate
    return None


def folder_label(name: str) -> str:
    """Strip a leading ``NNN.`` class-index prefix from a folder name."""
    return re.sub(r"^\d+\.", "", name)


def _norm(text: str) -> str:
    return re.sub(r"[\s\-]+", "_", text.strip().lower())


# --------------------------------------------------------------------------- #
# File integrity
# --------------------------------------------------------------------------- #
def open_image_rgb(path: Path) -> Image.Image:
    """Open an image as RGB, applying EXIF orientation."""
    with Image.open(path) as img:
        return ImageOps.exif_transpose(img).convert("RGB")


def file_check(path: Path, cfg: QualityConfig) -> tuple[bool, list[str], dict[str, int]]:
    """Cheap integrity gate run before the detector wastes time on the image."""
    reasons: list[str] = []
    meta: dict[str, int] = {}

    if not path.is_file():
        return False, ["file_missing"], meta

    try:
        if path.stat().st_size == 0:
            return False, ["file_empty"], meta
    except OSError:
        return False, ["file_missing"], meta

    try:
        img = open_image_rgb(path)
        meta["width"], meta["height"] = img.size
    except Exception as exc:  # noqa: BLE001 - corrupt files raise many types
        return False, [f"cannot_open:{type(exc).__name__}"], meta

    if meta["width"] < cfg.min_image_edge or meta["height"] < cfg.min_image_edge:
        reasons.append("image_too_small")

    return len(reasons) == 0, reasons, meta


# --------------------------------------------------------------------------- #
# YOLO bird detector (optional dependency)
# --------------------------------------------------------------------------- #
def ultralytics_available() -> bool:
    try:
        import ultralytics  # noqa: F401
    except Exception:  # noqa: BLE001 - import can fail many ways
        return False
    return True


def load_bird_detector(cfg: QualityConfig, *, required: bool = False) -> Any | None:
    """Load a YOLO detector, or return ``None`` if ultralytics is unavailable.

    With ``required=True`` a missing dependency raises instead of degrading.
    """
    if not ultralytics_available():
        if required:
            raise RuntimeError("ultralytics is not installed; run `uv sync --group training`.")
        print("[info] ultralytics unavailable; running without a bird detector.")
        return None

    from ultralytics import YOLO

    return YOLO(cfg.detector_model_name)


def _detections_from_yolo_result(
    result: Any, cfg: QualityConfig, *, rescue: bool
) -> list[dict[str, Any]]:
    """Extract bird detections from one Ultralytics result object."""
    names = result.names
    boxes = result.boxes
    if boxes is None:
        return []

    detections: list[dict[str, Any]] = []
    for box in boxes:
        class_id = int(box.cls.item())
        class_name = str(names.get(class_id, class_id)).lower()
        if class_name != cfg.bird_class_name:
            continue
        conf = float(box.conf.item())
        xyxy = [float(v) for v in box.xyxy.cpu().numpy().reshape(-1).tolist()]
        detections.append(
            {
                "class_id": class_id,
                "class_name": class_name,
                "conf": conf,
                "xyxy": xyxy,
                "rescue": rescue,
            }
        )

    detections.sort(key=lambda d: float(d["conf"]), reverse=True)
    return detections


def _predict_birds(
    path: Path, detector: Any, cfg: QualityConfig, *, conf: float, rescue: bool
) -> list[dict[str, Any]]:
    """Return bird detections (class name == ``bird``) sorted by confidence."""
    predict_kwargs: dict[str, Any] = {
        "source": str(path),
        "conf": conf,
        "verbose": False,
    }
    if cfg.detector_device:
        predict_kwargs["device"] = cfg.detector_device

    results = detector.predict(**predict_kwargs)
    if not results:
        return []
    return _detections_from_yolo_result(results[0], cfg, rescue=rescue)


def detect_birds(path: Path, detector: Any | None, cfg: QualityConfig) -> list[dict[str, Any]]:
    """Return bird detections, retrying at low confidence for review triage."""
    if detector is None:
        return []

    detections = _predict_birds(path, detector, cfg, conf=cfg.detector_conf, rescue=False)
    if detections or cfg.detector_rescue_conf >= cfg.detector_conf:
        return detections
    return _predict_birds(path, detector, cfg, conf=cfg.detector_rescue_conf, rescue=True)


def _predict_birds_batch(
    paths: Sequence[Path],
    detector: Any,
    cfg: QualityConfig,
    *,
    conf: float,
    rescue: bool,
) -> dict[Path, list[dict[str, Any]]]:
    if not paths:
        return {}

    predict_kwargs: dict[str, Any] = {
        "source": [str(path) for path in paths],
        "conf": conf,
        "verbose": False,
        "batch": max(1, cfg.detector_batch_size),
    }
    if cfg.detector_device:
        predict_kwargs["device"] = cfg.detector_device

    try:
        results = detector.predict(**predict_kwargs)
    except Exception as exc:  # noqa: BLE001 - fall back to per-image isolation
        print(f"[warn] batch detector failed, falling back to single-image mode: {exc}")
        return {
            path: _predict_birds(path, detector, cfg, conf=conf, rescue=rescue) for path in paths
        }

    by_path: dict[Path, list[dict[str, Any]]] = {}
    for path, result in zip(paths, results, strict=False):
        by_path[path] = _detections_from_yolo_result(result, cfg, rescue=rescue)
    return by_path


def detect_birds_batch(
    paths: Sequence[Path],
    detector: Any | None,
    cfg: QualityConfig,
) -> dict[Path, list[dict[str, Any]]]:
    """Batch bird detections with a low-confidence rescue pass for misses."""
    if detector is None or not paths:
        return {path: [] for path in paths}

    primary = _predict_birds_batch(paths, detector, cfg, conf=cfg.detector_conf, rescue=False)
    if cfg.detector_rescue_conf >= cfg.detector_conf:
        return primary

    missed = [path for path in paths if not primary.get(path)]
    rescue = _predict_birds_batch(missed, detector, cfg, conf=cfg.detector_rescue_conf, rescue=True)
    primary.update(rescue)
    return primary


# --------------------------------------------------------------------------- #
# Crop + quality metrics
# --------------------------------------------------------------------------- #
def pil_to_cv_rgb(img: Image.Image) -> Any:
    return np.asarray(img.convert("RGB"))


def rgb_to_gray(rgb: Any) -> Any:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def clip_bbox_xyxy(xyxy: Sequence[float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = xyxy
    x1 = max(0, min(width - 1, int(round(x1))))
    y1 = max(0, min(height - 1, int(round(y1))))
    x2 = max(0, min(width, int(round(x2))))
    y2 = max(0, min(height, int(round(y2))))
    return x1, y1, x2, y2


def crop_from_bbox(img: Image.Image, xyxy: Sequence[float], pad_frac: float = 0.08) -> Image.Image:
    width, height = img.size
    x1, y1, x2, y2 = clip_bbox_xyxy(xyxy, width, height)

    pad_x = int(round((x2 - x1) * pad_frac))
    pad_y = int(round((y2 - y1) * pad_frac))

    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(width, x2 + pad_x)
    y2 = min(height, y2 + pad_y)

    return img.crop((x1, y1, x2, y2))


def laplacian_var(gray: Any) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def exposure_stats(gray: Any) -> tuple[float, float]:
    under = float(np.mean(gray < 10))
    over = float(np.mean(gray > 245))
    return under, over


def dark_border_fraction(gray: Any, border_fraction: float = 0.08) -> float:
    height, width = gray.shape[:2]
    border = int(min(height, width) * border_fraction)
    if border <= 0:
        return 0.0

    mask = np.zeros(gray.shape[:2], dtype=bool)
    mask[:border, :] = True
    mask[-border:, :] = True
    mask[:, :border] = True
    mask[:, -border:] = True

    return float(np.mean(gray[mask] < 30))


def bbox_area_fraction(xyxy: Sequence[float], width: int, height: int) -> float:
    x1, y1, x2, y2 = clip_bbox_xyxy(xyxy, width, height)
    area = max(0, x2 - x1) * max(0, y2 - y1)
    denom = float(width * height)
    return float(area / denom) if denom > 0 else 0.0


def expand_bbox_xyxy(
    xyxy: Sequence[float], width: int, height: int, pad_frac: float
) -> list[float]:
    """Pad a detector bbox to include more body/context for review crops."""
    x1, y1, x2, y2 = clip_bbox_xyxy(xyxy, width, height)
    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)
    pad_x = int(round(box_w * pad_frac))
    pad_y = int(round(box_h * pad_frac))
    return [
        float(max(0, x1 - pad_x)),
        float(max(0, y1 - pad_y)),
        float(min(width, x2 + pad_x)),
        float(min(height, y2 + pad_y)),
    ]


def bbox_touches_frame(
    xyxy: Sequence[float], width: int, height: int, edge_frac: float
) -> bool:
    """Return True when a detector bbox reaches the image edge."""
    x1, y1, x2, y2 = clip_bbox_xyxy(xyxy, width, height)
    x_margin = max(2, int(round(width * edge_frac)))
    y_margin = max(2, int(round(height * edge_frac)))
    return x1 <= x_margin or y1 <= y_margin or x2 >= width - x_margin or y2 >= height - y_margin


def primary_reason(reasons: Sequence[str]) -> str | None:
    return reasons[0] if reasons else None


def coerce_bbox(value: Any) -> list[float] | None:
    """Coerce a bbox from None / NaN / string / list / ndarray into 4 floats."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"nan", "none", "null", "[]"}:
            return None
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            parts = [p for p in re.split(r"[,\s]+", text.strip("[]() ")) if p]
            try:
                value = [float(p) for p in parts]
            except ValueError:
                return None
    if isinstance(value, np.ndarray):
        value = value.reshape(-1).tolist()
    if isinstance(value, (list, tuple)):
        try:
            numbers = [float(x) for x in value]
        except (TypeError, ValueError):
            return None
        if len(numbers) != 4 or any(math.isnan(x) or math.isinf(x) for x in numbers):
            return None
        return numbers
    return None


# --------------------------------------------------------------------------- #
# Optional feature hooks (never break the base review)
# --------------------------------------------------------------------------- #
_IQA_METRIC: Any = None
_IQA_TRIED = False
_DINOV2_MODEL: Any = None
_DINOV2_TRIED = False


def score_image_quality(
    crop_rgb: Any, *, enable: bool, metric_name: str = "brisque"
) -> dict[str, float] | None:
    """Optional no-reference IQA score via ``pyiqa``. Returns None if disabled/absent."""
    global _IQA_METRIC, _IQA_TRIED
    if not enable:
        return None
    try:
        import torch  # noqa: PLC0415

        if not _IQA_TRIED:
            _IQA_TRIED = True
            import pyiqa  # noqa: PLC0415

            _IQA_METRIC = pyiqa.create_metric(metric_name, device="cpu")
        if _IQA_METRIC is None:
            return None
        tensor = (
            torch.from_numpy(np.ascontiguousarray(crop_rgb)).permute(2, 0, 1).unsqueeze(0).float()
            / 255.0
        )
        score = float(_IQA_METRIC(tensor).item())
        return {metric_name: score}
    except Exception as exc:  # noqa: BLE001 - optional path must never break review
        print(f"[warn] IQA scoring unavailable: {type(exc).__name__}: {exc}")
        return None


def extract_dinov2(crop_rgb: Any, *, enable: bool) -> Any | None:
    """Optional DINOv2 embedding via ``timm``. Returns an ndarray or None."""
    global _DINOV2_MODEL, _DINOV2_TRIED
    if not enable:
        return None
    try:
        import torch  # noqa: PLC0415

        if not _DINOV2_TRIED:
            _DINOV2_TRIED = True
            import timm  # noqa: PLC0415

            _DINOV2_MODEL = timm.create_model(
                "vit_small_patch14_dinov2.lvd142m", pretrained=True, num_classes=0
            ).eval()
        if _DINOV2_MODEL is None:
            return None
        pil = Image.fromarray(crop_rgb).resize((518, 518))
        tensor = (
            torch.from_numpy(np.ascontiguousarray(np.asarray(pil)))
            .permute(2, 0, 1)
            .unsqueeze(0)
            .float()
            / 255.0
        )
        with torch.no_grad():
            feats = _DINOV2_MODEL(tensor)
        return feats.reshape(-1).cpu().numpy()
    except Exception as exc:  # noqa: BLE001 - optional path must never break review
        print(f"[warn] DINOv2 extraction unavailable: {type(exc).__name__}: {exc}")
        return None


# --------------------------------------------------------------------------- #
# Per-image review (the decision gate)
# --------------------------------------------------------------------------- #
def _observation_id(record: dict[str, Any]) -> str | None:
    for key in OBSERVATION_ID_KEYS:
        value = record.get(key)
        if value:
            return str(value)
    prid = record.get("provider_record_id")
    if prid and ":" in str(prid):
        return str(prid).split(":", 1)[0]
    return str(prid) if prid else None


def _claimed_label(record: dict[str, Any]) -> str | None:
    for key in LABEL_KEYS:
        value = record.get(key)
        if value:
            return str(value)
    return None


def _class_folder(record: dict[str, Any], path: Path) -> str | None:
    value = record.get("class_folder")
    if value:
        return str(value)
    parent = path.parent.name
    return parent if parent else None


def _source_stage(record: dict[str, Any], path: Path) -> str | None:
    value = record.get("source_stage")
    if value:
        return str(value)
    parts = path.parts
    for stage in ("raw", "processed", "review", "quarantine"):
        if stage in parts:
            return stage
    return None


def _decision_for(reasons: list[str], cfg: QualityConfig) -> Decision:
    if not reasons:
        return "accepted"
    return "quarantine" if cfg.quarantine_instead_of_reject else "rejected"


def review_one_image(
    path: Path,
    record: dict[str, Any],
    detector: Any | None,
    cfg: QualityConfig,
    *,
    root: Path | None = None,
    dry: DryRunConfig | None = None,
    detections_override: list[dict[str, Any]] | None = None,
) -> ImageQualityReview:
    """Review a single image and return a decision with machine-readable reasons."""
    root = root or repo_root()
    rel_path = safe_relpath(path, root)
    claimed_label = _claimed_label(record)
    class_folder = _class_folder(record, path)
    source_stage = _source_stage(record, path)
    provider = record.get("provider")
    provider_observation_id = _observation_id(record)

    ok, file_reasons, file_meta = file_check(path, cfg)
    if not ok:
        return ImageQualityReview(
            image_path=rel_path,
            claimed_label=claimed_label,
            class_folder=class_folder,
            source_stage=source_stage,
            provider=provider,
            provider_observation_id=provider_observation_id,
            decision="rejected",
            reasons=file_reasons,
            primary_reason=primary_reason(file_reasons),
            width=file_meta.get("width"),
            height=file_meta.get("height"),
        )

    img = open_image_rgb(path)
    width, height = img.size
    full_gray = rgb_to_gray(pil_to_cv_rgb(img))
    dark_border = dark_border_fraction(full_gray)

    reasons: list[str] = []
    if dark_border > cfg.max_dark_border_frac:
        reasons.append("scope_or_dark_border_artefact")

    raw_detections = (
        detections_override
        if detections_override is not None
        else detect_birds(path, detector, cfg)
    )
    # Drop micro-detections below the detector floor (noise).
    detections = [
        d
        for d in raw_detections
        if bbox_area_fraction(d["xyxy"], width, height) >= cfg.min_bbox_area_frac_detector
    ]

    if not detections:
        if detector is None:
            reasons.append("detector_unavailable")
        else:
            reasons.append("manual_review_detector_missed")
            if class_folder or claimed_label:
                reasons.append("cutoff_or_obstruction")
        return ImageQualityReview(
            image_path=rel_path,
            claimed_label=claimed_label,
            class_folder=class_folder,
            source_stage=source_stage,
            provider=provider,
            provider_observation_id=provider_observation_id,
            decision=_decision_for(reasons, cfg),
            reasons=reasons,
            primary_reason=primary_reason(reasons),
            width=width,
            height=height,
            bird_detections=0,
            dark_border_frac=dark_border,
        )

    if len(detections) > cfg.max_bird_detections_for_classifier:
        reasons.append("multiple_birds")

    best = detections[0]
    detector_xyxy = [float(v) for v in best["xyxy"]]
    xyxy = expand_bbox_xyxy(detector_xyxy, width, height, cfg.bbox_pad_frac)
    detector_area_frac = bbox_area_fraction(detector_xyxy, width, height)
    area_frac = bbox_area_fraction(xyxy, width, height)
    rescue_used = bool(best.get("rescue"))
    detector_conf = float(best["conf"])

    if bbox_touches_frame(detector_xyxy, width, height, cfg.edge_touch_frac):
        reasons.append("cutoff_subject")
    if rescue_used or detector_conf < cfg.obstruction_conf_threshold:
        reasons.append("obstruction")
    if detector_area_frac < cfg.min_bbox_area_frac_classifier:
        reasons.append("subject_too_small")
    if area_frac > cfg.max_bbox_area_frac:
        reasons.append("bbox_implausibly_large")

    crop = crop_from_bbox(img, xyxy, pad_frac=0.0)
    crop_rgb = pil_to_cv_rgb(crop)
    crop_gray = rgb_to_gray(crop_rgb)

    lap_var = laplacian_var(crop_gray)
    contrast_std = float(crop_gray.std())
    under, over = exposure_stats(crop_gray)

    if lap_var < cfg.min_laplacian_var:
        reasons.append("blurry_subject")
    if contrast_std < cfg.min_crop_contrast_std:
        reasons.append("low_subject_contrast")
    if under > cfg.max_underexposed_frac:
        reasons.append("silhouette_or_underexposed_subject")
    if over > cfg.max_overexposed_frac:
        reasons.append("overexposed_subject")

    iqa_scores = score_image_quality(crop_rgb, enable=bool(dry and dry.enable_iqa))
    dinov2 = extract_dinov2(crop_rgb, enable=bool(dry and dry.enable_dinov2))

    return ImageQualityReview(
        image_path=rel_path,
        claimed_label=claimed_label,
        class_folder=class_folder,
        source_stage=source_stage,
        provider=provider,
        provider_observation_id=provider_observation_id,
        decision=_decision_for(reasons, cfg),
        reasons=reasons,
        primary_reason=primary_reason(reasons),
        width=width,
        height=height,
        detector_conf=detector_conf,
        detector_rescue_used=rescue_used,
        bird_detections=len(detections),
        detector_bbox_xyxy=detector_xyxy,
        bbox_xyxy=xyxy,
        detector_bbox_area_frac=detector_area_frac,
        bbox_area_frac=area_frac,
        crop_laplacian_var=lap_var,
        crop_contrast_std=contrast_std,
        crop_underexposed_frac=under,
        crop_overexposed_frac=over,
        dark_border_frac=dark_border,
        iqa_scores=iqa_scores,
        dinov2_dim=int(dinov2.shape[0]) if dinov2 is not None else None,
    )


# --------------------------------------------------------------------------- #
# Discovery + class selection
# --------------------------------------------------------------------------- #
def _record_matches_class(record: dict[str, Any], token_norm: str) -> bool:
    for key in ("label", "common_name", "scientific_name", "class_name"):
        value = record.get(key)
        if value and token_norm in _norm(str(value)):
            return True
    class_id = record.get("class_id")
    return class_id is not None and token_norm == str(class_id)


def auto_pick_class(raw_root: Path, processed_root: Path, min_images: int) -> str | None:
    """Pick the first class folder (sorted) that has at least ``min_images`` images."""
    best_name: str | None = None
    best_count = -1
    for base in (raw_root, processed_root):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            count = sum(1 for _ in iter_image_files_fast([child]))
            if count >= min_images:
                return child.name
            if count > best_count:
                best_name, best_count = child.name, count
    return best_name


def select_class_images(
    token: str,
    records: Sequence[dict[str, Any]],
    *,
    raw_root: Path,
    processed_root: Path,
    roots: Sequence[Path] | None = None,
    max_images: int,
) -> list[tuple[Path, dict[str, Any]]]:
    """Collect ``(path, record)`` pairs for one class, metadata-first then scan.

    Metadata records that resolve to a real file are preferred (they carry the
    label / provider id). Any remaining images in the matching folders are added
    with a folder-derived label so nothing on disk is silently skipped.
    """
    token_norm = _norm(token)
    selected: list[tuple[Path, dict[str, Any]]] = []
    seen: set[str] = set()

    for record in records:
        if not _record_matches_class(record, token_norm):
            continue
        resolved = resolve_image_path(record, roots=roots)
        if resolved is None:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        selected.append((resolved, record))

    for base in (raw_root, processed_root):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or token_norm not in _norm(child.name):
                continue
            label = folder_label(child.name)
            for img in iter_image_files_fast([child]):
                key = str(img)
                if key in seen:
                    continue
                seen.add(key)
                selected.append((img, {"label": label}))

    selected.sort(key=lambda pair: str(pair[0]).lower())
    return selected[:max_images]


def select_all_class_images(
    raw_root: Path,
    *,
    max_images: int = 0,
) -> list[tuple[Path, dict[str, Any]]]:
    """Collect all raster images from every raw class folder.

    ``max_images <= 0`` means no cap. Originals remain in ``raw``; later copy
    steps write sorted review copies elsewhere.
    """
    selected: list[tuple[Path, dict[str, Any]]] = []
    for class_dir in sorted(raw_root.iterdir() if raw_root.is_dir() else []):
        if not class_dir.is_dir():
            continue
        class_folder = class_dir.name
        label = folder_label(class_folder)
        for img in iter_image_files_fast([class_dir]):
            selected.append(
                (
                    img,
                    {
                        "label": label,
                        "class_folder": class_folder,
                        "source_stage": "raw",
                    },
                )
            )
            if max_images > 0 and len(selected) >= max_images:
                return selected
    selected.sort(key=lambda pair: str(pair[0]).lower())
    return selected


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def _abs_image_path(image_path: str, root: Path) -> Path:
    candidate = Path(image_path)
    return candidate if candidate.is_absolute() else root / candidate


def write_review_jsonl(rows: Sequence[ImageQualityReview], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) + "\n")


def write_review_csv(rows: Sequence[ImageQualityReview], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [f.name for f in fields(ImageQualityReview)]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            record = asdict(row)
            for key in ("reasons", "detector_bbox_xyxy", "bbox_xyxy", "iqa_scores"):
                value = record.get(key)
                record[key] = json.dumps(value) if value not in (None, []) else ""
            writer.writerow(record)


def build_contact_sheet(
    rows: Sequence[ImageQualityReview],
    path: Path,
    *,
    root: Path,
    cols: int = 4,
    max_examples: int = 12,
    thumb: float = 4.0,
) -> Any:
    """Render a labelled contact sheet with bbox overlays and save it to ``path``."""
    from matplotlib.figure import Figure  # noqa: PLC0415
    from matplotlib.patches import Rectangle  # noqa: PLC0415

    subset = list(rows[:max_examples])
    path.parent.mkdir(parents=True, exist_ok=True)

    if not subset:
        fig = Figure(figsize=(6, 2))
        ax = fig.add_subplot(1, 1, 1)
        ax.text(0.5, 0.5, "No images reviewed", ha="center", va="center")
        ax.axis("off")
        fig.savefig(path, dpi=110)
        return fig

    n_rows = math.ceil(len(subset) / cols)
    fig = Figure(figsize=(thumb * cols, thumb * n_rows))
    for index, review in enumerate(subset):
        ax = fig.add_subplot(n_rows, cols, index + 1)
        ax.axis("off")
        try:
            with Image.open(_abs_image_path(review.image_path, root)) as img:
                ax.imshow(np.asarray(img.convert("RGB")))
        except Exception:  # noqa: BLE001 - a bad image must not break the sheet
            ax.text(0.5, 0.5, "unreadable", ha="center", va="center")

        bbox = coerce_bbox(review.bbox_xyxy)
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            ax.add_patch(
                Rectangle(
                    (x1, y1),
                    x2 - x1,
                    y2 - y1,
                    fill=False,
                    linewidth=2,
                    edgecolor="lime",
                )
            )

        reason_text = ", ".join(review.reasons[:2]) if review.reasons else "ok"
        ax.set_title(f"{review.decision}\n{reason_text}", fontsize=8)

    fig.tight_layout()
    fig.savefig(path, dpi=110)
    return fig


def safe_path_segment(text: str | None, fallback: str = "unknown") -> str:
    cleaned = _norm(text or fallback).replace("/", "_")
    return cleaned or fallback


def copy_review_images(
    rows: Sequence[ImageQualityReview],
    review_root: Path,
    *,
    root: Path,
    reason_subdirs: bool = True,
) -> int:
    """Copy, never move, reviewed images into sorted review directories."""
    import shutil  # noqa: PLC0415

    copied = 0
    for review in rows:
        src = _abs_image_path(review.image_path, root)
        if not src.is_file():
            continue
        class_segment = safe_path_segment(review.class_folder or review.claimed_label)
        dst_dir = review_root / review.decision / class_segment
        if reason_subdirs and review.decision != "accepted":
            dst_dir = dst_dir / safe_path_segment(review.primary_reason, "needs_review")
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
            copied += 1
    return copied


def batched_pairs(
    pairs: Sequence[tuple[Path, dict[str, Any]]], chunk_size: int
) -> Iterator[Sequence[tuple[Path, dict[str, Any]]]]:
    size = max(1, chunk_size)
    for start in range(0, len(pairs), size):
        yield pairs[start : start + size]


def review_selected_images(
    selected: Sequence[tuple[Path, dict[str, Any]]],
    detector: Any | None,
    cfg: QualityConfig,
    *,
    root: Path,
    dry: DryRunConfig,
) -> list[ImageQualityReview]:
    """Review selected images, using batched detector inference where possible."""
    rows: list[ImageQualityReview] = []
    total = len(selected)
    progress_every = max(1, _env_int("BIRDIDEX_PROGRESS_EVERY", 250))

    if detector is None:
        for path, record in selected:
            rows.append(review_one_image(path, record, detector, cfg, root=root, dry=dry))
        return rows

    for chunk in batched_pairs(selected, cfg.detector_chunk_size):
        paths = [path for path, _ in chunk]
        detections = detect_birds_batch(paths, detector, cfg)
        for path, record in chunk:
            rows.append(
                review_one_image(
                    path,
                    record,
                    detector,
                    cfg,
                    root=root,
                    dry=dry,
                    detections_override=detections.get(path, []),
                )
            )

        if total >= progress_every and len(rows) % progress_every < len(chunk):
            print(f"[progress] reviewed {len(rows)}/{total}")

    return rows


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
@dataclass
class ReviewResult:
    target_class: str | None
    rows: list[ImageQualityReview]
    decisions: Counter[str]
    reasons: Counter[str]
    jsonl_path: Path
    csv_path: Path
    contact_sheet_path: Path
    detector_model: str | None
    detector_device: str | None
    copied: int = 0


def run_dry_review(
    cfg: QualityConfig | None = None,
    dry: DryRunConfig | None = None,
    *,
    records: Sequence[dict[str, Any]] | None = None,
    detector: Any | None = None,
) -> ReviewResult:
    """Run a dry review over a handful of images from a single class.

    Produces the JSONL, CSV, and contact-sheet reports and returns a summary.
    Never deletes or moves originals.
    """
    cfg = cfg or QualityConfig.from_env()
    dry = dry or DryRunConfig.from_env()

    root = repo_root()
    images_root = images_dir()
    raw_root = images_root / "raw"
    processed_root = images_root / "processed"
    reports = reports_dir()

    if records is None:
        records_path = image_records_path()
        records = read_jsonl(records_path) if records_path.is_file() else []

    target_class = None
    max_images = max(0, dry.max_images)

    selected: list[tuple[Path, dict[str, Any]]] = []
    if dry.all_classes:
        selected = select_all_class_images(raw_root, max_images=max_images)
        target_class = "ALL_CLASSES"
    else:
        target_class = dry.review_class or auto_pick_class(
            raw_root, processed_root, max(1, max_images)
        )

    if target_class and not dry.all_classes:
        selected = select_class_images(
            target_class,
            records,
            raw_root=raw_root,
            processed_root=processed_root,
            max_images=max_images or 12,
        )

    if detector is None and ultralytics_available():
        detector = load_bird_detector(cfg)

    rows = review_selected_images(selected, detector, cfg, root=root, dry=dry)

    if dry.all_classes:
        suffix = "all_sample" if max_images > 0 else "all"
        jsonl_path = reports / f"dataset_quality_review_{suffix}.jsonl"
        csv_path = reports / f"dataset_quality_review_{suffix}.csv"
        contact_sheet_path = reports / f"dataset_quality_contact_sheet_{suffix}.png"
    else:
        jsonl_path = reports / REPORT_JSONL
        csv_path = reports / REPORT_CSV
        contact_sheet_path = reports / REPORT_CONTACT_SHEET

    write_review_jsonl(rows, jsonl_path)
    write_review_csv(rows, csv_path)
    build_contact_sheet(rows, contact_sheet_path, root=root)

    copied = 0
    if dry.copy_images:
        copied = copy_review_images(
            rows,
            images_root / "review",
            root=root,
            reason_subdirs=dry.reason_subdirs,
        )

    return ReviewResult(
        target_class=target_class,
        rows=rows,
        decisions=Counter(row.decision for row in rows),
        reasons=Counter(reason for row in rows for reason in row.reasons),
        jsonl_path=jsonl_path,
        csv_path=csv_path,
        contact_sheet_path=contact_sheet_path,
        detector_model=cfg.detector_model_name if detector is not None else None,
        detector_device=cfg.detector_device if detector is not None else None,
        copied=copied,
    )


def print_summary(result: ReviewResult) -> None:
    root = repo_root()
    print(f"target class      : {result.target_class}")
    print(f"detector model    : {result.detector_model or '(none / unavailable)'}")
    print(f"detector device   : {result.detector_device or '(cpu / unavailable)'}")
    device_info = torch_device_summary()
    if device_info.get("torch_available"):
        print(
            "torch backend     : "
            f"{device_info.get('backend')} "
            f"(torch {device_info.get('torch_version')}, hip {device_info.get('hip_version')})"
        )
        for device in device_info.get("devices", []):
            name = device.get("name", "unknown")
            memory = device.get("total_memory_gb")
            arch = device.get("gcn_arch_name")
            print(f"    device {device.get('index')}: {name}; {memory} GB; {arch}")
    print(f"images reviewed   : {len(result.rows)}")
    print(f"images copied     : {result.copied}")
    print("decisions         :")
    for decision in ("accepted", "quarantine", "rejected"):
        print(f"    {decision:11s}: {result.decisions.get(decision, 0)}")
    print("reasons           :")
    if result.reasons:
        for reason, count in result.reasons.most_common():
            print(f"    {reason:34s}: {count}")
    else:
        print("    (none)")
    print("outputs           :")
    for output in (result.jsonl_path, result.csv_path, result.contact_sheet_path):
        print(f"    {safe_relpath(output, root)}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: run the review headlessly and print a summary."""
    import argparse  # noqa: PLC0415

    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="review every raw class folder")
    parser.add_argument("--class", dest="review_class", help="class label or folder substring")
    parser.add_argument(
        "--max-images",
        type=int,
        default=None,
        help="maximum images to review; 0 means no cap in --all mode",
    )
    parser.add_argument(
        "--copy-images",
        action="store_true",
        help="copy reviewed images into data/images/review without touching raw",
    )
    parser.add_argument(
        "--flat-reasons",
        action="store_true",
        help="do not create primary-reason subfolders for quarantine/rejected copies",
    )
    args = parser.parse_args(argv)

    dry = DryRunConfig.from_env()
    if args.all:
        dry = DryRunConfig(
            enabled=False,
            all_classes=True,
            review_class=None,
            max_images=0 if args.max_images is None else args.max_images,
            detector_model=dry.detector_model,
            copy_images=True,
            reason_subdirs=not args.flat_reasons,
            enable_iqa=dry.enable_iqa,
            enable_dinov2=dry.enable_dinov2,
        )
    elif args.review_class or args.max_images is not None or args.copy_images or args.flat_reasons:
        dry = DryRunConfig(
            enabled=True,
            all_classes=False,
            review_class=args.review_class or dry.review_class,
            max_images=dry.max_images if args.max_images is None else args.max_images,
            detector_model=dry.detector_model,
            copy_images=args.copy_images or dry.copy_images,
            reason_subdirs=not args.flat_reasons,
            enable_iqa=dry.enable_iqa,
            enable_dinov2=dry.enable_dinov2,
        )

    result = run_dry_review(dry=dry)
    print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
