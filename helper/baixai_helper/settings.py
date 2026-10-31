"""Preferências do usuário, guardadas no SQLite."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .errors import BaixaiError
from .paths import default_download_dir

DEFAULTS = {
    "download_dir": "",  # vazio = ~/Downloads/Baixai
    "organize_by_platform": True,
    "organize_by_author": False,
    "max_concurrent": 2,
    "default_height": 1080,
    "default_container": "mp4",
    "default_mp3_bitrate": 192,
    "default_image_format": "original",
    "playlist_confirm_threshold": 20,
    "ffmpeg_path": "",
    "ytdlp_path": "",
    "gallerydl_path": "",
}


class Settings:
    def __init__(self, store):
        self._store = store

    def all(self) -> dict:
        data = dict(DEFAULTS)
        raw = self._store.get_kv("settings")
        if raw:
            try:
                data.update({k: v for k, v in json.loads(raw).items() if k in DEFAULTS})
            except json.JSONDecodeError:
                pass
        return data

    def get(self, key: str):
        return self.all()[key]

    def update(self, changes: dict) -> dict:
        cur = self.all()
        if "download_dir" in changes and changes["download_dir"]:
            changes = {**changes, "download_dir": str(self._check_dir(changes["download_dir"]))}
        for key in ("ffmpeg_path", "ytdlp_path", "gallerydl_path"):
            if changes.get(key):
                p = Path(changes[key]).expanduser()
                if not (p.is_file() and os.access(p, os.X_OK)):
                    raise BaixaiError("invalid_path", f"O arquivo informado em {key} não existe ou não é executável.")
                changes[key] = str(p)
        cur.update(changes)
        self._store.set_kv("settings", json.dumps(cur))
        return cur

    def download_dir(self) -> Path:
        v = self.get("download_dir")
        p = Path(v).expanduser() if v else default_download_dir()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def _check_dir(value: str) -> Path:
        p = Path(value).expanduser()
        if not p.is_absolute():
            raise BaixaiError("invalid_path", "A pasta de destino deve ser um caminho absoluto.")
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise BaixaiError("invalid_path", "Não foi possível criar ou acessar a pasta de destino.") from None
        if not os.access(p, os.W_OK):
            raise BaixaiError("invalid_path", "Sem permissão de escrita na pasta de destino.")
        return p.resolve()
