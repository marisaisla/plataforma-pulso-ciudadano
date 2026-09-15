"""Configuración local de conexiones privadas, fuera de la base de datos."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
SETTINGS_PATH = BASE_DIR / ".env"


def get_setting(key: str) -> str:
    if os.getenv(key):
        return os.environ[key]
    if not SETTINGS_PATH.exists():
        return ""
    for line in SETTINGS_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def save_settings(values: dict[str, str]) -> None:
    existing = {}
    if SETTINGS_PATH.exists():
        for line in SETTINGS_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                existing[key.strip()] = value.strip()
    for key, value in values.items():
        if value.strip():
            existing[key] = value.strip()
    body = [
        "# Configuración privada local - no compartir este archivo.",
        *[f"{key}={value}" for key, value in sorted(existing.items())],
        "",
    ]
    SETTINGS_PATH.write_text("\n".join(body), encoding="utf-8")


def import_private_setting(key: str, source_path: Path) -> bool:
    """Import one named secret from another local configuration without displaying it."""
    if not source_path.exists():
        return False
    value = ""
    for line in source_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip()
            break
    if not value:
        return False
    save_settings({key: value})
    return True
