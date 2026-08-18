"""Installed-resource and per-user data paths."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


PRODUCT_DIRECTORY = "SpaceMouseCodex"


def resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def user_data_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return root / PRODUCT_DIRECTORY


def user_config_path() -> Path:
    return user_data_directory() / "mapping.json"


def user_settings_path() -> Path:
    return user_data_directory() / "settings.json"


def user_log_path() -> Path:
    return user_data_directory() / "logs" / "app.log"


def ensure_user_config() -> Path:
    destination = user_config_path()
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    bundled = resource_path("config", "mapping.json")
    if bundled.is_file():
        shutil.copyfile(bundled, destination)
    else:
        from .mapping import MappingConfig

        MappingConfig().save(destination)
    return destination

