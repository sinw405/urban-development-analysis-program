from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings


def load_yaml_rule(filename: str) -> dict[str, Any]:
    rule_path = get_settings().rules_dir / filename
    if not rule_path.exists():
        raise FileNotFoundError(f"Rule file not found: {rule_path}")

    with rule_path.open("r", encoding="utf-8") as rule_file:
        data = yaml.safe_load(rule_file) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Rule file must contain a YAML mapping: {rule_path}")

    return data


def get_rule_path(filename: str) -> Path:
    return get_settings().rules_dir / filename
