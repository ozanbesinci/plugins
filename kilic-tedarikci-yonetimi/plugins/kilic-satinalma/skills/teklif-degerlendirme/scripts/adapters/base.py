from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class Unit:
    unit_type: str
    unit_index: int
    locator: dict[str, Any]
    text: str = ""
    structured: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParseResult:
    parser_name: str
    status: str
    units: list[Unit]
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "parser_name": self.parser_name,
            "status": self.status,
            "units": [u.as_dict() for u in self.units],
            "notes": self.notes,
            "metadata": self.metadata,
        }


def unsupported(path: Path, reason: str) -> ParseResult:
    return ParseResult("unsupported", "unreadable", [], [reason], {"filename": path.name})
