from typing import Dict
from .adapters.base import BaseAdapter
import importlib.metadata


def discover_adapters() -> Dict[str, BaseAdapter]:
    """Discover adapters via entry points."""
    adapters = {}
    try:
        for ep in importlib.metadata.entry_points(group="osi.adapters"):
            adapters[ep.name] = ep.load()()
    except Exception:
        pass
    return adapters