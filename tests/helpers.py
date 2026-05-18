from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_yaml(path: Path | str) -> dict[str, Any]:
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        msg = f"Expected dict, got {type(data).__name__}"
        raise ValueError(msg)
    return data


def load_json(path: Path | str) -> dict[str, Any]:
    import json

    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        msg = f"Expected dict, got {type(data).__name__}"
        raise ValueError(msg)
    return data


def list_fixtures(subdir: str, suffix: str = ".yaml") -> list[Path]:
    """List all fixture files in tests/fixtures/<subdir>/."""
    directory = FIXTURES_DIR / subdir
    if not directory.is_dir():
        return []
    return sorted(directory.glob(f"*{suffix}"))


def fixture_path(subdir: str, name: str) -> Path:
    return FIXTURES_DIR / subdir / name


def assert_dict_subset(expected: dict, actual: dict, path: str = "") -> None:
    """Check that all keys in expected exist in actual with matching values."""
    for key, expected_val in expected.items():
        current_path = f"{path}.{key}" if path else key
        assert key in actual, f"Missing key: {current_path}"
        actual_val = actual[key]
        if isinstance(expected_val, dict) and isinstance(actual_val, dict):
            assert_dict_subset(expected_val, actual_val, current_path)
        else:
            assert actual_val == expected_val, (
                f"Mismatch at {current_path}: expected {expected_val!r}, got {actual_val!r}"
            )


def assert_osi_model_valid(osi_dict: dict) -> None:
    """Verify an OSI model dict has the basic required structure."""
    assert "version" in osi_dict, "Missing version"
    assert "semantic_model" in osi_dict, "Missing semantic_model"
    assert isinstance(osi_dict["semantic_model"], list), "semantic_model must be a list"
    for sm in osi_dict["semantic_model"]:
        assert "name" in sm, "Semantic model missing name"
        assert "datasets" in sm, f"Semantic model '{sm.get('name')}' missing datasets"
        for ds in sm["datasets"]:
            assert "name" in ds, "Dataset missing name"
            assert "fields" in ds, f"Dataset '{ds.get('name')}' missing fields"
            for f in ds["fields"]:
                assert "name" in f, "Field missing name"
                assert "expression" in f, f"Field '{f.get('name')}' missing expression"
