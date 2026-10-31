import os
import threading
import time

import pytest

from baixai_helper.engines.base import JobSpec, Result
from baixai_helper.errors import BaixaiError, Cancelled


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("BAIXAI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    monkeypatch.delenv("BAIXAI_ALLOW_PRIVATE_NETWORK", raising=False)
    monkeypatch.delenv("BAIXAI_ALLOWED_IDS", raising=False)
    yield


@pytest.fixture
def offline(monkeypatch):
    """Evita DNS nos testes da fila (a validação de rede é testada à parte)."""
    monkeypatch.setenv("BAIXAI_ALLOW_PRIVATE_NETWORK", "1")


def wait_for(cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        v = cond()
        if v:
            return v
        time.sleep(0.02)
    raise AssertionError("tempo esgotado")


class FakeEngine:
    """Mecanismo falso: só para a lógica da fila (nunca usado para afirmar downloads reais)."""

    def __init__(self, behavior="ok"):
        self.behavior = behavior
        self.calls = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.running = 0
        self.max_running = 0
        self._lock = threading.Lock()

    def download(self, spec: JobSpec, outdir, ctx):
        with self._lock:
            self.calls.append(spec.id)
            self.running += 1
            self.max_running = max(self.max_running, self.running)
        try:
            self.started.set()
            if self.behavior == "fail":
                raise BaixaiError("network", "falha simulada", retryable=True)
            if self.behavior == "crash":
                raise RuntimeError("boom")
            if self.behavior in ("slow", "gate"):
                while not (self.release.is_set() if self.behavior == "gate" else False):
                    ctx.check()
                    ctx.progress(0.3, "downloading")
                    time.sleep(0.02)
            ctx.progress(0.5, "downloading")
            f = outdir / "../escape.bin"  # tentativa de path traversal deve ser neutralizada pela fila
            f = outdir / "arquivo.bin"
            f.write_bytes(b"x" * 10)
            return Result(files=[f])
        finally:
            with self._lock:
                self.running -= 1
