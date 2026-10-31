"""Interface comum dos adaptadores e execução segura de subprocessos."""
from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..errors import Cancelled
from ..tools import child_env


@dataclass
class JobSpec:
    id: str
    url: str
    platform: str
    engine: str
    mode: str
    options: dict
    meta: dict = field(default_factory=dict)


@dataclass
class Result:
    files: list[Path]
    title: str | None = None
    author: str | None = None
    notes: list[str] = field(default_factory=list)


class RunContext:
    """Canal entre o adaptador e a fila: progresso, logs e cancelamento."""

    def __init__(self, cancel: threading.Event, on_progress: Callable[..., None], on_log: Callable[[str], None], settings: dict, tools):
        self.cancel = cancel
        self._on_progress = on_progress
        self._on_log = on_log
        self.settings = settings
        self.tools = tools
        self._procs: set[subprocess.Popen] = set()
        self._lock = threading.Lock()

    @property
    def cancelled(self) -> bool:
        return self.cancel.is_set()

    def check(self) -> None:
        if self.cancelled:
            raise Cancelled()

    def progress(self, fraction: float | None, stage: str = "downloading", detail: str | None = None, speed: float | None = None, eta: float | None = None) -> None:
        self._on_progress(fraction, stage, detail, speed, eta)

    def log(self, line: str) -> None:
        self._on_log(line)


def popen_flags() -> dict:
    """Opções de criação de processo por sistema: grupo próprio (POSIX) ou sem janela de console (Windows)."""
    if os.name == "posix":
        return {"start_new_session": True}
    return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def _kill_tree_windows(proc: subprocess.Popen) -> None:
    # taskkill /T encerra também os filhos (ffmpeg iniciado pelo yt-dlp, por exemplo).
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        proc.kill()


def kill_process(proc: subprocess.Popen, grace: float = 3.0) -> None:
    if proc.poll() is not None:
        return
    if os.name != "posix":
        _kill_tree_windows(proc)
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.kill()
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=grace)
    except (subprocess.TimeoutExpired, ProcessLookupError, PermissionError):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def run_streaming(cmd: list[str], ctx: RunContext, on_line: Callable[[str], None], cwd: Path | None = None, tail: int = 40) -> tuple[int, list[str]]:
    """Executa `cmd` (lista de argumentos, sem shell) lendo stdout+stderr linha a linha.

    Cancela de forma cooperativa: ao detectar o cancelamento encerra o grupo de processos.
    """
    kwargs: dict = popen_flags()
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=child_env(),
        cwd=str(cwd) if cwd else None, shell=False, text=True, encoding="utf-8", errors="replace", bufsize=1, **kwargs,
    )
    q: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        assert proc.stdout
        for line in proc.stdout:
            q.put(line.rstrip("\r\n"))
        q.put(None)

    threading.Thread(target=reader, daemon=True).start()
    last: list[str] = []
    done = False
    try:
        while not done:
            if ctx.cancelled:
                kill_process(proc)
                raise Cancelled()
            try:
                line = q.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                done = True
                break
            last.append(line)
            del last[:-tail]
            on_line(line)
        rc = proc.wait()
    finally:
        if proc.poll() is None:
            kill_process(proc)
    if ctx.cancelled:
        raise Cancelled()
    return rc, last


def run_capture(cmd: list[str], timeout: float = 120, max_bytes: int = 60_000_000) -> tuple[int, str, str]:
    """Executa e captura a saída (para análises). Sem shell; ambiente reduzido."""
    kwargs: dict = popen_flags()
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=child_env(), shell=False, **kwargs
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_process(proc)
        proc.communicate()
        raise
    if len(out) > max_bytes:
        out = out[:max_bytes]
    return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def fmt_bytes(n: float | int | None) -> str:
    if not n:
        return ""
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""
