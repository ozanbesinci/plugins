"""Kılıç Sözleşme Yönetimi: P1 local registry, not a legal approval engine."""
from .errors import CoreError
from .store import Store

__all__ = ["Store", "CoreError"]
from .runtime_identity import component_policy
__version__ = component_policy()["core_version"]
