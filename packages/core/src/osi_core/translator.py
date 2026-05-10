from typing import Dict, Mapping, Optional, Union
from pathlib import Path

from .models import ResolvedModel
from .models.types import ParseResult
from .resolver import resolve
from .adapters.base import BaseAdapter


class Translator:
    def __init__(self, adapters: Mapping[str, BaseAdapter]):
        self.adapters: Dict[str, BaseAdapter] = dict(adapters)

    def translate(
        self,
        source: Union[Path, str],
        from_format: str,
        to_format: str,
        input_version: Optional[str] = None,
        output_version: Optional[str] = None,
    ) -> str:
        """Translate from one format to another via ResolvedModel."""
        in_adapter = self.adapters.get(from_format)
        if not in_adapter:
            raise KeyError(f"No adapter for format: {from_format}")
        out_adapter = self.adapters.get(to_format)
        if not out_adapter:
            raise KeyError(f"No adapter for format: {to_format}")

        parse_result = in_adapter.parse(source, input_version)
        model = resolve(parse_result)
        return out_adapter.translate(model, output_version)

    def parse_to_model(
        self, source: Union[Path, str], format: str, version: Optional[str] = None
    ) -> ResolvedModel:
        """Parse source to ResolvedModel without writing."""
        adapter = self.adapters.get(format)
        if not adapter:
            raise KeyError(f"No adapter for format: {format}")
        parse_result = adapter.parse(source, version)
        return resolve(parse_result)