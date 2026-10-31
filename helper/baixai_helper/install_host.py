"""Instalação e remoção do manifesto do host Native Messaging (por usuário, sem privilégios)."""
from __future__ import annotations

import json
import os
import re
import stat
import sys
from pathlib import Path

from . import HOST_NAME, paths
from .errors import BaixaiError

ID_RE = re.compile(r"^[a-p]{32}$")
_DIRS = {
    "darwin": {"chrome": "Google/Chrome", "chromium": "Chromium", "edge": "Microsoft Edge", "brave": "BraveSoftware/Brave-Browser"},
    "linux": {"chrome": "google-chrome", "chromium": "chromium", "edge": "microsoft-edge", "brave": "BraveSoftware/Brave-Browser"},
}
_REG = {"chrome": r"Software\Google\Chrome", "chromium": r"Software\Chromium", "edge": r"Software\Microsoft\Edge", "brave": r"Software\BraveSoftware\Brave-Browser"}
BROWSERS = tuple(_REG)


def manifest_path(browser: str) -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support" / _DIRS["darwin"][browser] / "NativeMessagingHosts" / f"{HOST_NAME}.json"
    if sys.platform == "win32":
        return paths.subdir("native-messaging") / f"{HOST_NAME}.json"
    return Path.home() / ".config" / _DIRS["linux"][browser] / "NativeMessagingHosts" / f"{HOST_NAME}.json"


def build_manifest(exec_path: str, ids: list[str]) -> dict:
    return {
        "name": HOST_NAME,
        "description": "Baixaí — aplicativo auxiliar local para baixar mídia",
        "path": exec_path,
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{i}/" for i in ids],
    }


def write_dev_wrapper(python: str) -> str:
    """Script de inicialização usado em desenvolvimento (o Chrome precisa de um executável)."""
    if sys.platform == "win32":
        p = paths.subdir("bin") / "baixai-host.bat"
        p.write_text(f'@echo off\r\n"{python}" -I -X utf8 -m baixai_helper host %*\r\n', encoding="utf-8")
        return str(p)
    p = paths.subdir("bin") / "baixai-host"
    extra = os.environ.get("BAIXAI_TOOLS_PATH", "")
    lines = ["#!/bin/sh"]
    if extra:
        lines.append(f"export BAIXAI_TOOLS_PATH='{extra}'")
    lines.append(f"exec '{python}' -I -X utf8 -m baixai_helper host \"$@\"")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    return str(p)


def install(exec_path: str, ids: list[str], browsers: list[str]) -> list[str]:
    if not ids or any(not ID_RE.match(i) for i in ids):
        raise BaixaiError("invalid_id", "ID de extensão inválido (esperado: 32 letras de a a p).")
    exe = Path(exec_path)
    if not exe.is_absolute() or not exe.is_file():
        raise BaixaiError("invalid_path", f"Executável do host não encontrado: {exec_path}")
    written: list[str] = []
    manifest = json.dumps(build_manifest(str(exe), ids), indent=2, ensure_ascii=False)
    (paths.data_dir() / "host_config.json").write_text(json.dumps({"allowed_ids": ids}))
    for b in browsers:
        if b not in BROWSERS:
            raise BaixaiError("invalid_browser", f"Navegador desconhecido: {b}")
        mp = manifest_path(b)
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(manifest, encoding="utf-8")
        if sys.platform == "win32":
            import winreg  # type: ignore

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{_REG[b]}\NativeMessagingHosts\{HOST_NAME}") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, str(mp))
        written.append(str(mp))
    return written


def uninstall(browsers: list[str], purge_data: bool = False) -> list[str]:
    removed: list[str] = []
    for b in browsers:
        mp = manifest_path(b)
        if mp.exists():
            mp.unlink()
            removed.append(str(mp))
        if sys.platform == "win32":
            import winreg  # type: ignore

            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{_REG[b]}\NativeMessagingHosts\{HOST_NAME}")
            except OSError:
                pass
    cfg = paths.data_dir() / "host_config.json"
    if cfg.exists():
        cfg.unlink()
    if purge_data:
        import shutil

        shutil.rmtree(paths.data_dir(), ignore_errors=True)
        removed.append(str(paths.data_dir()))
    return removed


def status() -> list[dict]:
    out = []
    for b in BROWSERS:
        mp = manifest_path(b)
        if not mp.exists():
            continue
        try:
            m = json.loads(mp.read_text())
        except ValueError:
            out.append({"browser": b, "manifest": str(mp), "valid": False})
            continue
        out.append({"browser": b, "manifest": str(mp), "valid": True, "path": m.get("path"), "path_exists": Path(m.get("path", "")).is_file(),
                    "allowed_origins": m.get("allowed_origins")})
    return out
