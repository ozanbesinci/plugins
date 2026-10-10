from __future__ import annotations

from pathlib import Path

from adapters.base import ParseResult, Unit


def parse(path: Path) -> ParseResult:
    try:
        from PIL import Image, ExifTags
        with Image.open(path) as im:
            exif = im.getexif() or {}
            orientation = None
            for key, value in exif.items():
                if ExifTags.TAGS.get(key) == "Orientation":
                    orientation = value
                    break
            meta = {
                "width": im.width,
                "height": im.height,
                "mode": im.mode,
                "format": im.format,
                "orientation": orientation,
                "requires_vision": True,
            }
    except Exception as exc:
        return ParseResult("Pillow", "unreadable", [], [str(exc)])
    unit = Unit("image", 1, {"region": [0, 0, meta["width"], meta["height"]]}, "", meta)
    return ParseResult("Pillow", "partial", [unit], ["Image content requires vision/OCR for semantic extraction."], meta)
