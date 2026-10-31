"""Pastas de dados do aplicativo (por usuário, fora da pasta de downloads)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("BAIXAI_DATA_DIR")
    if override:
        p = Path(override)
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "Baixai"
    elif sys.platform == "win32":
        p = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Baixai"
    else:
        p = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "baixai"
    p.mkdir(parents=True, exist_ok=True)
    return p


def subdir(name: str) -> Path:
    p = data_dir() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def default_download_dir() -> Path:
    return Path.home() / "Downloads" / "Baixai"
