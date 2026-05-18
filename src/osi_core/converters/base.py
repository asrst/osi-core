from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseConverter(ABC):
    VENDOR_NAME: str

    @abstractmethod
    def to_osi(self, native_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Convert a native vendor model to an OSI-compatible dict."""

    @abstractmethod
    def from_osi(self, osi_model: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Convert an OSI model dict to the native vendor format."""
