from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class ApplicationReference:
    name: str
    confidence: str


@dataclass(slots=True)
class ExtractedProcess:
    process_name: str
    process_id: str
    org_unit: str
    follows_after: list[str]
    applications: list[ApplicationReference]
    source_path: str


class Extractor(Protocol):
    def extract(self, source_path: Path) -> ExtractedProcess:
        ...

