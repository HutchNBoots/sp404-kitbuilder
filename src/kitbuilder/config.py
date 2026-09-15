"""Load categories.yaml (the user-tunable classification/layout config)."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_FILENAME = "categories.yaml"


def packaged_default_config_path() -> Path:
    """Path to the config shipped inside the installed package."""
    return resources.files("kitbuilder") / DEFAULT_CONFIG_FILENAME


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load a categories.yaml. Falls back to the packaged default if path is None."""
    config_path = Path(path) if path is not None else packaged_default_config_path()
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data.setdefault("pads_per_bank", 16)
    data.setdefault("banks_per_kit_max", 2)
    data.setdefault("weak_kit_category_threshold", 3)
    data.setdefault("categories", {})
    data.setdefault("exclude_folders", [])
    data.setdefault("extensions", [".wav", ".aiff", ".aif"])
    return data
