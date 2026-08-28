from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

PATTERNS_PATH = os.getenv(
    "ROOT_CAUSE_PATTERNS_PATH",
    str(Path(__file__).resolve().parent / "patterns.yaml"),
)
ROOT_CAUSE_CONFIDENCE_THRESHOLD = 0.80


@dataclass
class RootCauseDiagnosis:
    category: str | None
    confidence: float
    matched_pattern: str | None = None
    matched_log: str | None = None

    @property
    def requires_human(self) -> bool:
        return self.confidence < ROOT_CAUSE_CONFIDENCE_THRESHOLD

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "matched_pattern": self.matched_pattern,
            "matched_log": self.matched_log,
            "requires_human": self.requires_human,
        }


def _load_categories(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return (yaml.safe_load(file) or {}).get("categories", {})


def diagnose(logs: list[dict], path: str = PATTERNS_PATH) -> RootCauseDiagnosis:
    categories = _load_categories(path)
    compiled = {
        category: [
            (re.compile(pattern, re.IGNORECASE), pattern)
            for pattern in info.get("patterns", [])
        ]
        for category, info in categories.items()
    }

    for log in logs:
        message = log.get("message", "")
        for category, patterns in compiled.items():
            for compiled_pattern, raw_pattern in patterns:
                if compiled_pattern.search(message):
                    return RootCauseDiagnosis(
                        category=category,
                        confidence=float(categories[category]["confidence"]),
                        matched_pattern=raw_pattern,
                        matched_log=message,
                    )

    return RootCauseDiagnosis(category=None, confidence=0.0)
