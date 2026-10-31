"""Loop do host Native Messaging (stdin/stdout com prefixo de 32 bits)."""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import BinaryIO

from . import paths
from .errors import BaixaiError, ProtocolError
from .protocol import MessageTooLarge, encode_message, read_message, validate_request
from .redact import redact
from .service import Service

log = logging.getLogger("baixai.host")
ORIGIN_PREFIX = "chrome-extension://"


def allowed_extension_ids() -> list[str]:
    env = os.environ.get("BAIXAI_ALLOWED_IDS")
    if env:
        return [x for x in env.split(",") if x]
    cfg = paths.data_dir() / "host_config.json"
    try:
        return list(json.loads(cfg.read_text())["allowed_ids"])
    except (OSError, ValueError, KeyError):
        return []


def origin_allowed(origin: str | None, ids: list[str]) -> bool:
    if not origin or not origin.startswith(ORIGIN_PREFIX):
        return False
    ext_id = origin[len(ORIGIN_PREFIX):].strip("/")
    return ext_id in ids


def setup_logging() -> None:
    from logging.handlers import RotatingFileHandler

    class Redacting(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            record.msg = redact(record.getMessage(), max_len=800)
            record.args = ()
            return True

    h = RotatingFileHandler(paths.data_dir() / "helper.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    h.addFilter(Redacting())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(logging.INFO)


class Host:
    def __init__(self, stdin: BinaryIO, stdout: BinaryIO, service_factory=Service):
        self.stdin, self.stdout = stdin, stdout
        self._wlock = threading.Lock()
        self.service = service_factory(emit=self.send)
        self.pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="cmd")

    def send(self, obj: dict) -> None:
        try:
            data = encode_message(obj)
        except MessageTooLarge:
            data = encode_message({"id": obj.get("id"), "ok": False, "error": {"code": "too_large", "message": "Resposta maior que o limite do canal."}})
        with self._wlock:
            try:
                self.stdout.write(data)
                self.stdout.flush()
            except (BrokenPipeError, ValueError, OSError):
                pass

    def _dispatch(self, mid, cmd: str, payload: dict) -> None:
        try:
            data = self.service.handle(cmd, payload)
            self.send({"id": mid, "ok": True, "data": data})
        except BaixaiError as e:
            self.send({"id": mid, "ok": False, "error": e.to_dict()})
        except Exception:
            log.exception("falha no comando %s", cmd)
            self.send({"id": mid, "ok": False, "error": {"code": "internal", "message": "Erro interno do aplicativo local. Veja o log do aplicativo.", "retryable": False}})

    def run(self) -> int:
        self.service.start()
        try:
            while True:
                try:
                    msg = read_message(self.stdin)
                except ProtocolError as e:
                    if e.code in ("bad_frame",):
                        self.send({"id": None, "ok": False, "error": e.to_dict()})
                        break
                    self.send({"id": None, "ok": False, "error": e.to_dict()})
                    continue
                if msg is None:
                    break
                try:
                    mid, cmd, payload = validate_request(msg)
                except ProtocolError as e:
                    mid = msg.get("id") if isinstance(msg.get("id"), str) else None
                    self.send({"id": mid, "ok": False, "error": e.to_dict()})
                    continue
                self.pool.submit(self._dispatch, mid, cmd, payload)
        finally:
            self.service.shutdown()
            self.pool.shutdown(wait=False, cancel_futures=True)
        return 0


def main(origin: str | None) -> int:
    """Ponto de entrada quando o Chrome inicia o host."""
    setup_logging()
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    sys.stdout = sys.stderr  # nada além do protocolo pode ir para o stdout real
    if sys.platform == "win32":
        import msvcrt

        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)  # type: ignore[attr-defined]
        msvcrt.setmode(1, os.O_BINARY)  # type: ignore[attr-defined]
    ids = allowed_extension_ids()
    if not origin_allowed(origin, ids):
        log.warning("origem recusada: %s", origin)
        stdout.write(encode_message({"event": "fatal", "error": {"code": "origin_not_allowed", "message": "Esta extensão não está autorizada a usar o aplicativo local."}}))
        stdout.flush()
        return 2
    log.info("host iniciado (origem %s)", origin)
    return Host(stdin, stdout).run()
