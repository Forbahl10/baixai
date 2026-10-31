"""Protocolo de mensagens: enquadramento do Native Messaging e validação de esquema.

Chrome → host aceita até 64 MiB; host → Chrome, até 1 MB. Aqui as mensagens são pequenas
(comandos, status e progresso): limitamos a entrada a 256 KiB e a saída a 900 KB.
Os arquivos de mídia nunca passam por este canal.
"""
from __future__ import annotations

import json
import re
import struct
from typing import Any, BinaryIO

from .errors import ProtocolError

MAX_IN = 256 * 1024
MAX_OUT = 900_000

MODES = ("video", "audio", "image")


class MessageTooLarge(Exception):
    pass


# ---------------------------------------------------------------- enquadramento
def read_message(stream: BinaryIO) -> dict | None:
    """Lê uma mensagem; None em EOF. Mensagens grandes demais são descartadas com erro."""
    header = stream.read(4)
    if not header:
        return None
    if len(header) < 4:
        raise ProtocolError("bad_frame", "Cabeçalho de mensagem incompleto.")
    (n,) = struct.unpack("=I", header)
    if n > MAX_IN:
        remaining = n
        while remaining > 0:
            chunk = stream.read(min(65536, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
        raise ProtocolError("message_too_large", "Mensagem maior que o limite aceito.")
    data = b""
    while len(data) < n:
        chunk = stream.read(n - len(data))
        if not chunk:
            raise ProtocolError("bad_frame", "Mensagem truncada.")
        data += chunk
    try:
        obj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProtocolError("bad_json", "A mensagem não é um JSON válido.") from None
    if not isinstance(obj, dict):
        raise ProtocolError("bad_json", "A mensagem deve ser um objeto JSON.")
    return obj


def encode_message(obj: Any) -> bytes:
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_OUT:
        raise MessageTooLarge(len(data))
    return struct.pack("=I", len(data)) + data


# ---------------------------------------------------------------- validação
def _fail(path: str, msg: str):
    raise ProtocolError("invalid_payload", f"Campo inválido ({path or 'raiz'}): {msg}")


def validate(spec: dict, value: Any, path: str = "") -> Any:
    t = spec["t"]
    if value is None and spec.get("null"):
        return None
    if t == "str":
        if not isinstance(value, str):
            _fail(path, "esperado texto")
        if len(value) > spec.get("max", 2048):
            _fail(path, "texto longo demais")
        if "pattern" in spec and not re.fullmatch(spec["pattern"], value):
            _fail(path, "formato inesperado")
        return value
    if t == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(path, "esperado número inteiro")
        if not spec.get("min", -(2**31)) <= value <= spec.get("max", 2**31):
            _fail(path, "fora do intervalo")
        if "one_of" in spec and value not in spec["one_of"]:
            _fail(path, "valor não permitido")
        return value
    if t == "bool":
        if not isinstance(value, bool):
            _fail(path, "esperado verdadeiro/falso")
        return value
    if t == "enum":
        if value not in spec["v"]:
            _fail(path, "valor não permitido")
        return value
    if t == "list":
        if not isinstance(value, list) or len(value) > spec.get("max", 1000):
            _fail(path, "lista inválida ou grande demais")
        return [validate(spec["of"], v, f"{path}[{i}]") for i, v in enumerate(value)]
    if t == "obj":
        if not isinstance(value, dict):
            _fail(path, "esperado objeto")
        req, opt = spec.get("req", {}), spec.get("opt", {})
        for k in value:
            if k not in req and k not in opt:
                _fail(f"{path}.{k}".lstrip("."), "campo desconhecido")
        out = {}
        for k, s in req.items():
            if k not in value:
                _fail(f"{path}.{k}".lstrip("."), "campo obrigatório ausente")
            out[k] = validate(s, value[k], f"{path}.{k}".lstrip("."))
        for k, s in opt.items():
            if k in value:
                out[k] = validate(s, value[k], f"{path}.{k}".lstrip("."))
        return out
    raise AssertionError(t)


S = lambda mx=2048, **k: {"t": "str", "max": mx, **k}  # noqa: E731
I = lambda lo, hi, **k: {"t": "int", "min": lo, "max": hi, **k}  # noqa: E731
B = {"t": "bool"}
ID = S(64, pattern=r"[A-Za-z0-9_-]{1,64}")

OPTIONS = {
    "t": "obj",
    "opt": {
        "height": I(1, 8640),
        "container": {"t": "enum", "v": ["mp4", "original"]},
        "audio_format": {"t": "enum", "v": ["mp3", "original"]},
        "mp3_bitrate": I(64, 320, one_of=[96, 128, 160, 192, 256, 320]),
        "image_format": {"t": "enum", "v": ["original", "jpeg", "png"]},
        "items": {"t": "list", "of": I(1, 100000), "max": 2000},
        "engine": {"t": "enum", "v": ["ytdlp", "gallerydl", "direct"]},
    },
}
META = {"t": "obj", "opt": {"title": S(400), "author": S(200), "thumbnail": S(2048), "platform": S(30), "count": I(0, 100000)}}
MODE = {"t": "enum", "v": list(MODES)}

SETTINGS = {
    "t": "obj",
    "opt": {
        "download_dir": S(1024),
        "organize_by_platform": B,
        "organize_by_author": B,
        "max_concurrent": I(1, 5),
        "default_height": I(144, 4320),
        "default_container": {"t": "enum", "v": ["mp4", "original"]},
        "default_mp3_bitrate": I(64, 320, one_of=[96, 128, 160, 192, 256, 320]),
        "default_image_format": {"t": "enum", "v": ["original", "jpeg", "png"]},
        "playlist_confirm_threshold": I(1, 1000),
        "ffmpeg_path": S(1024),
        "ytdlp_path": S(1024),
        "gallerydl_path": S(1024),
    },
}

COMMANDS: dict[str, dict] = {
    "hello": {"t": "obj"},
    "analyze": {"t": "obj", "req": {"url": S()}},
    "enqueue": {"t": "obj", "req": {"url": S(), "mode": MODE}, "opt": {"options": OPTIONS, "meta": META, "force": B}},
    "enqueue_batch": {
        "t": "obj",
        "req": {"entries": {"t": "list", "of": {"t": "obj", "req": {"url": S()}, "opt": {"meta": META}}, "max": 200}, "mode": MODE},
        "opt": {"options": OPTIONS, "force": B},
    },
    "list_jobs": {"t": "obj", "opt": {"limit": I(1, 500)}},
    "cancel": {"t": "obj", "req": {"id": ID}},
    "retry": {"t": "obj", "req": {"id": ID}},
    "remove": {"t": "obj", "req": {"id": ID}},
    "reveal": {"t": "obj", "req": {"id": ID}},
    "job_log": {"t": "obj", "req": {"id": ID}},
    "clear_history": {"t": "obj"},
    "get_settings": {"t": "obj"},
    "set_settings": {"t": "obj", "req": {"settings": SETTINGS}},
    "choose_folder": {"t": "obj"},
    "tools_status": {"t": "obj", "opt": {"refresh": B}},
    "tools_check_updates": {"t": "obj"},
    "tools_update_ytdlp": {"t": "obj"},
}


def validate_request(msg: dict) -> tuple[str | None, str, dict]:
    """Valida o envelope {id, cmd, payload}. Retorna (id, cmd, payload limpo)."""
    mid = msg.get("id")
    if mid is not None:
        validate(ID, mid, "id")
    unknown = set(msg) - {"id", "cmd", "payload"}
    if unknown:
        raise ProtocolError("invalid_payload", "Campos desconhecidos na mensagem.")
    cmd = msg.get("cmd")
    if not isinstance(cmd, str) or cmd not in COMMANDS:
        raise ProtocolError("unknown_command", "Comando desconhecido.")
    payload = validate(COMMANDS[cmd], msg.get("payload", {}), "payload")
    return mid, cmd, payload
