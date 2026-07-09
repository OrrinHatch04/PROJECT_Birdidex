#!/usr/bin/env python3
"""Static safety and structure checks for BIRDIDEX notebooks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_HEADINGS: tuple[str, ...] = (
    "## 1. Title / Project Context",
    "## 2. Reproducibility Setup",
    "## 3. Data Layout Audit",
    "## 4. Class Index Loading",
    "## 5. Region and Species Prior Audit",
    "## 6. Image Metadata Audit",
    "## 7. Image Quality and Preprocessing Logic",
    "## 8. Split Audit and Creation Logic",
    "## 9. Baseline Model Scaffold",
    "## 10. Evaluation Scaffold",
    "## 11. Confidence Gate",
    "## 12. Species Profile Integration",
    "## 13. Observation Logging Schema",
    "## 14. Device Runtime Logic",
    "## 15. CLI Integration",
    "## 16. Final Checklist",
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OpenAI-style token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    (
        "hard-coded API key or token assignment",
        re.compile(r"(?i)(api[_-]?key|access[_-]?token)\b\s*=\s*['\"][^'\"]{8,}['\"]"),
    ),
    (
        "hard-coded master seed assignment",
        re.compile(
            r"(?i)\b(BIRDIDEX_MASTER_SEED|master[_-]?seed)\b\s*[:=]\s*"
            r"((['\"][^'\"]{6,}['\"])|(\d{6,}))"
        ),
    ),
)

LOCAL_PATH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Linux home path", re.compile(r"/home/[^\s'\"`]+")),
    ("macOS home path", re.compile(r"/Users/[^\s'\"`]+")),
    ("Windows user path", re.compile(r"[A-Za-z]:\\\\Users\\\\[^\s'\"`]+")),
)


def _cell_source(cell: dict[str, Any]) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)


def load_notebook(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid notebook JSON: {exc}") from exc
    if not isinstance(payload.get("cells"), list):
        raise ValueError(f"{path} does not contain a notebook cells list")
    return payload


def validate_notebook(path: Path) -> list[str]:
    notebook = load_notebook(path)
    text = "\n".join(_cell_source(cell) for cell in notebook["cells"])
    lower_text = text.lower()
    issues: list[str] = []

    for heading in REQUIRED_HEADINGS:
        if heading.lower() not in lower_text:
            issues.append(f"missing required heading: {heading}")

    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            issues.append(f"possible {name}")

    for name, pattern in LOCAL_PATH_PATTERNS:
        if pattern.search(text):
            issues.append(f"absolute local path found: {name}")

    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook", type=Path, help="Notebook path to validate.")
    args = parser.parse_args(argv)

    issues = validate_notebook(args.notebook)
    if issues:
        for issue in issues:
            print(f"[FAIL] {issue}")
        return 1
    print(f"[OK] notebook static checks passed: {args.notebook}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
