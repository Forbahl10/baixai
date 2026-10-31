"""Sanitização de nomes e caminhos: sem path traversal, sem sobrescrita."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .errors import BaixaiError

_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_RESERVED = {
    "con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10)),
}


def _truncate_bytes(s: str, limit: int) -> str:
    raw = s.encode("utf-8")
    if len(raw) <= limit:
        return s
    return raw[:limit].decode("utf-8", errors="ignore")


def sanitize_component(name: str, *, max_bytes: int = 150, fallback: str = "arquivo") -> str:
    """Um único componente de caminho, seguro em macOS, Windows e Linux."""
    s = unicodedata.normalize("NFC", str(name or ""))
    s = _FORBIDDEN.sub("_", s)
    s = re.sub(r"\s+", " ", s).strip().strip(".")
    s = s.lstrip(".")  # nada de arquivos ocultos nem "..".
    if not s:
        return fallback
    if s.split(".")[0].lower() in _RESERVED:
        s = "_" + s
    return _truncate_bytes(s, max_bytes).rstrip(" .") or fallback


def sanitize_filename(name: str, *, max_bytes: int = 180) -> str:
    """Sanitiza preservando uma extensão curta e simples."""
    p = Path(str(name or "").replace("\\", "/").split("/")[-1])
    stem, ext = p.stem, p.suffix
    if not re.fullmatch(r"\.[A-Za-z0-9]{1,8}", ext or ""):
        stem, ext = p.name, ""
    stem = sanitize_component(stem, max_bytes=max_bytes - len(ext.encode()))
    return stem + ext.lower()


def safe_join(base: Path, *parts: str) -> Path:
    """Junta componentes já sanitizados e garante que o resultado fica dentro de `base`."""
    base_r = Path(base).resolve()
    target = base_r.joinpath(*[sanitize_component(p) for p in parts]).resolve()
    if target != base_r and base_r not in target.parents:
        raise BaixaiError("path_escape", "Caminho de destino inválido.")
    return target


def unique_path(path: Path) -> Path:
    """Nunca sobrescreve: acrescenta ' (1)', ' (2)'... se o nome já existir."""
    if not path.exists():
        return path
    for i in range(1, 10_000):
        cand = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not cand.exists():
            return cand
    raise BaixaiError("path_exhausted", "Não foi possível encontrar um nome livre para o arquivo.")
