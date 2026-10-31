"""Localização, versões e atualização explícita das ferramentas externas.

Nada é baixado ou atualizado sem uma ação explícita do usuário (`tools_update_ytdlp`).
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import paths
from .errors import BaixaiError
from .urlsafe import safe_open

_ENV_ALLOW = (
    "PATH", "HOME", "USER", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR", "SYSTEMROOT", "LANG", "LC_ALL",
    "PATHEXT", "COMSPEC", "WINDIR", "SYSTEMDRIVE", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROCESSOR_ARCHITECTURE", "HOMEDRIVE", "HOMEPATH",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
)
MIN_VERSIONS = {"deno": (2, 3, 0), "node": (22, 0, 0), "bun": (1, 2, 11)}
FROZEN = bool(getattr(sys, "frozen", False))


def extra_dirs() -> list[str]:
    dirs = [d for d in os.environ.get("BAIXAI_TOOLS_PATH", "").split(os.pathsep) if d]
    dirs += [str(paths.data_dir() / "bin"), "/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local/bin"), str(Path.home() / ".deno/bin")]
    if sys.platform == "win32":  # winget, Chocolatey e Scoop colocam atalhos aqui; o Chrome pode não ter o PATH novo
        local, pdata = os.environ.get("LOCALAPPDATA", ""), os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        dirs += [str(Path(local) / "Microsoft" / "WinGet" / "Links"), str(Path(pdata) / "chocolatey" / "bin"), str(Path.home() / "scoop" / "shims"),
                 r"C:\ffmpeg\bin", str(Path.home() / ".deno" / "bin")]
    return dirs


def search_path() -> str:
    return os.pathsep.join(dict.fromkeys([*extra_dirs(), *os.environ.get("PATH", "").split(os.pathsep)]))


def find_exe(name: str) -> str | None:
    return shutil.which(name, path=search_path())


def child_env() -> dict:
    env = {k: os.environ[k] for k in _ENV_ALLOW if k in os.environ}
    env["PATH"] = search_path()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run_version(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=child_env(), stdin=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else None
    except (OSError, subprocess.SubprocessError):
        return None


def _vtuple(s: str) -> tuple[int, ...]:
    m = re.search(r"(\d+(?:\.\d+)+)", s or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


# ------------------------------------------------------------- comandos dos mecanismos
def _module_cmd(module: str, frozen_name: str) -> list[str] | None:
    if FROZEN:
        return [sys.executable, "--engine", frozen_name]
    if importlib.util.find_spec(module):
        return [sys.executable, "-I", "-X", "utf8", "-m", module]
    return None


def engine_cmd(engine: str, settings: dict) -> tuple[list[str], str] | None:
    """Retorna (prefixo do comando, origem) para 'ytdlp' ou 'gallerydl'."""
    key, module, frozen_name, managed = {
        "ytdlp": ("ytdlp_path", "yt_dlp", "yt-dlp", paths.data_dir() / "engines" / ("yt-dlp.exe" if sys.platform == "win32" else "yt-dlp")),
        "gallerydl": ("gallerydl_path", "gallery_dl", "gallery-dl", None),
    }[engine]
    if settings.get(key):
        return [settings[key]], "configurado"
    if managed and managed.is_file():
        return [str(managed)], "atualizado pelo usuário"
    cmd = _module_cmd(module, frozen_name)
    if cmd:
        return cmd, "embutido" if FROZEN else "módulo Python"
    return None


def ffmpeg_path(settings: dict) -> str | None:
    if settings.get("ffmpeg_path"):
        return settings["ffmpeg_path"]
    return os.environ.get("BAIXAI_FFMPEG") or find_exe("ffmpeg")


def js_runtime() -> dict:
    for name in ("deno", "node", "bun"):
        exe = find_exe(name)
        if not exe:
            continue
        ver = _run_version([exe, "--version"]) or ""
        vt = _vtuple(ver)
        if vt and vt >= MIN_VERSIONS[name]:
            return {"ok": True, "name": name, "path": exe, "version": ".".join(map(str, vt))}
    return {"ok": False, "name": None, "path": None, "version": None}


class Tools:
    def __init__(self, settings):
        self._settings = settings
        self._cache: tuple[float, dict] | None = None

    def status(self, refresh: bool = False) -> dict:
        if self._cache and not refresh and time.time() - self._cache[0] < 60:
            return self._cache[1]
        s = self._settings.all()
        out = {"ytdlp": self._engine_status("ytdlp", s), "gallerydl": self._engine_status("gallerydl", s)}
        ff = ffmpeg_path(s)
        out["ffmpeg"] = {"ok": bool(ff), "path": ff, "version": (_run_version([ff, "-version"]) or "").replace("ffmpeg version", "").strip()[:60] if ff else None}
        out["js_runtime"] = js_runtime()
        out["python"] = {"version": sys.version.split()[0], "frozen": FROZEN}
        self._cache = (time.time(), out)
        return out

    def invalidate(self) -> None:
        self._cache = None

    @staticmethod
    def _engine_status(engine: str, settings: dict) -> dict:
        found = engine_cmd(engine, settings)
        if not found:
            return {"ok": False, "version": None, "source": None}
        cmd, source = found
        dist = {"ytdlp": "yt-dlp", "gallerydl": "gallery-dl"}[engine]
        version = None
        if source in ("módulo Python",):
            try:
                version = importlib.metadata.version(dist)
            except importlib.metadata.PackageNotFoundError:
                pass
        if version is None:
            version = _run_version([*cmd, "--version"])
        return {"ok": version is not None, "version": version, "source": source}


# ------------------------------------------------------------- atualização explícita do yt-dlp
def _asset_name() -> str:
    if sys.platform == "darwin":
        return "yt-dlp_macos"
    if sys.platform == "win32":
        return "yt-dlp.exe"
    import platform

    return "yt-dlp_linux_aarch64" if platform.machine().lower() in ("aarch64", "arm64") else "yt-dlp_linux"


def _http_get(url: str, limit: int) -> bytes:
    r = safe_open(url, timeout=60)
    try:
        if r.status != 200:
            raise BaixaiError("update_failed", f"O servidor respondeu com status {r.status}.")
        buf = bytearray()
        while chunk := r.read(1 << 16):
            buf += chunk
            if len(buf) > limit:
                raise BaixaiError("update_failed", "Arquivo maior que o esperado.")
        return bytes(buf)
    finally:
        r.close()


def check_updates(settings: dict) -> dict:
    cur = Tools._engine_status("ytdlp", settings).get("version")
    latest = json.loads(_http_get("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest", 2_000_000))["tag_name"]
    return {"ytdlp": {"current": cur, "latest": latest, "update_available": bool(cur) and _vtuple(latest) > _vtuple(cur)}}


def update_ytdlp(settings: dict) -> dict:
    """Baixa o binário oficial do yt-dlp, confere o SHA-256 publicado e o instala em data_dir/engines."""
    tag = json.loads(_http_get("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest", 2_000_000))["tag_name"]
    base = f"https://github.com/yt-dlp/yt-dlp/releases/download/{tag}"
    name = _asset_name()
    sums = _http_get(f"{base}/SHA2-256SUMS", 200_000).decode()
    expected = next((ln.split()[0] for ln in sums.splitlines() if ln.split()[-1:] == [name]), None)
    if not expected:
        raise BaixaiError("update_failed", "Não foi possível obter o checksum oficial desta versão.")
    blob = _http_get(f"{base}/{name}", 80_000_000)
    if hashlib.sha256(blob).hexdigest() != expected:
        raise BaixaiError("update_failed", "O checksum SHA-256 não confere; a atualização foi descartada.")
    dest_dir = paths.subdir("engines")
    dest = dest_dir / ("yt-dlp.exe" if sys.platform == "win32" else "yt-dlp")
    tmp = dest.with_suffix(".new")
    tmp.write_bytes(blob)
    tmp.chmod(0o755)
    ver = _run_version([str(tmp), "--version"])
    if not ver:
        tmp.unlink(missing_ok=True)
        raise BaixaiError("update_failed", "O arquivo baixado não executou corretamente; a atualização foi descartada.")
    os.replace(tmp, dest)
    return {"version": ver, "path": str(dest), "sha256": expected}
