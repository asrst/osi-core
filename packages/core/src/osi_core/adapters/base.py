from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union

from ..models import ResolvedModel
from ..models.types import ParseResult


class BaseAdapter(ABC):
    format_name: str

    @abstractmethod
    def parse(
        self, source: Union[Path, str], version: Optional[str] = None
    ) -> ParseResult:
        """Parse platform format into a ParseResult."""

    @abstractmethod
    def translate(
        self, model: ResolvedModel, target_version: Optional[str] = None
    ) -> str:
        """Write ResolvedModel to platform format string."""