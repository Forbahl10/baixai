"""Remoção de dados sensíveis de textos que vão para logs ou para a interface."""
from __future__ import annotations

import re
from pathlib import Path

_URL = re.compile(r"(https?://[^\s'\"<>?#]+)(?:[?#][^\s'\"<>]*)?", re.I)
_SECRET_KV = re.compile(
    r"(?i)\b(authorization|cookie|set-cookie|x-csrf-token|password|passwd|token|access_token|sessionid|csrftoken)\b(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")


def redact(text: str, *, max_len: int = 600) -> str:
    if not text:
        return ""
    out = _URL.sub(lambda m: m.group(1), text)  # descarta query string e fragmento
    out = _BEARER.sub(lambda m: f"{m.group(1)} ***", out)
    out = _SECRET_KV.sub(lambda m: f"{m.group(1)}{m.group(2)}***", out)
    home = str(Path.home())
    if home and home != "/":
        out = out.replace(home, "~")
    out = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", out)
    return out if len(out) <= max_len else out[: max_len - 1] + "…"
