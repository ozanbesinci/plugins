"""Kılıç Sözleşme Yönetimi: P1 local registry, not a legal approval engine."""
from .errors import CoreError
from .store import Store

__all__ = ["Store", "CoreError"]
__version__ = "0.1.0-dev.3"
