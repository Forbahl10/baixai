"""Instalação opcional e verificada de FFmpeg e Deno na pasta de dados do usuário (sem sudo/administrador).

Só roda quando o usuário pede (`baixai tools install-deps`). Cada arquivo vem de uma URL fixa deste módulo e é conferido
contra o SHA-256 fixado aqui antes de qualquer extração. FFmpeg e Deno NÃO são distribuídos junto com o aplicativo:
os builds abaixo são GPL-3.0 (FFmpeg: martin-riedl.de e Gyan) e MIT (Deno).
"""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import paths
from .errors import BaixaiError
from .urlsafe import safe_open

FFMPEG_VERSION = "9.0.2"
DENO_VERSION = "2.9.8"
_MR = "https://ffmpeg.martin-riedl.de/download"
_DENO = f"https://github.com/denoland/deno/releases/download/v{DENO_VERSION}"
_GYAN = f"https://github.com/GyanD/codexffmpeg/releases/download/{FFMPEG_VERSION}/ffmpeg-{FFMPEG_VERSION}-essentials_build.zip"


@dataclass(frozen=True)
class Artifact:
    url: str
    sha256: str
    wanted: tuple[str, ...]  # nomes (sem pasta) a extrair do ZIP, ex.: ("ffmpeg",)
    size_mb: int


# chave: "<so>-<arquitetura>"
FFMPEG: dict[str, tuple[Artifact, ...]] = {
    "macos-arm64": (
        Artifact(f"{_MR}/macos/arm64/1789931890_{FFMPEG_VERSION}/ffmpeg.zip", "c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924", ("ffmpeg",), 25),
        Artifact(f"{_MR}/macos/arm64/1789931890_{FFMPEG_VERSION}/ffprobe.zip", "fcbe839537485eaee7a7a8bc5cbc0f90d53617e80943e8a5b2e31cb851197ea6", ("ffprobe",), 25),
    ),
    "macos-x86_64": (
        Artifact(f"{_MR}/macos/amd64/1789931006_{FFMPEG_VERSION}/ffmpeg.zip", "7c6b4125b191cbf773832dc51f424cf2b6bb7da43007d1e066f95909e47cacd4", ("ffmpeg",), 25),
        Artifact(f"{_MR}/macos/amd64/1789931006_{FFMPEG_VERSION}/ffprobe.zip", "2322438ed2f6319a691291b247d09c69dcaa3a982460d1f269a7e1af335cfdfd", ("ffprobe",), 25),
    ),
    "linux-x86_64": (
        Artifact(f"{_MR}/linux/amd64/1789931100_{FFMPEG_VERSION}/ffmpeg.zip", "fa8ecf4abbd290d98f7d188b8649cc6b391ae209a98452be955a15aab1909d7f", ("ffmpeg",), 40),
        Artifact(f"{_MR}/linux/amd64/1789931100_{FFMPEG_VERSION}/ffprobe.zip", "3f428c49070be3d24ec338602b76d412e401ffcb8a5641ef0e729181a232fc32", ("ffprobe",), 40),
    ),
    "linux-arm64": (
        Artifact(f"{_MR}/linux/arm64/1789931697_{FFMPEG_VERSION}/ffmpeg.zip", "93a76ae90db5474eecdf951a729857c64f3de23567228d6a7d5e6e8e3cd1021b", ("ffmpeg",), 40),
        Artifact(f"{_MR}/linux/arm64/1789931697_{FFMPEG_VERSION}/ffprobe.zip", "bcbe80fb741c180083327afaf5434812e006b33cacde2016b9aeaf6936128330", ("ffprobe",), 40),
    ),
    # sha256 conferido em duas fontes independentes (gyan.dev e o campo digest da Release no GitHub)
    "windows-x86_64": (Artifact(_GYAN, "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba", ("ffmpeg.exe", "ffprobe.exe"), 114),),
}

DENO: dict[str, tuple[Artifact, ...]] = {
    "macos-arm64": (Artifact(f"{_DENO}/deno-aarch64-apple-darwin.zip", "9f0bf660393da2eaff044cdc7444cb08c73f235849b61d224d825a194ce7c98e", ("deno",), 39),),
    "macos-x86_64": (Artifact(f"{_DENO}/deno-x86_64-apple-darwin.zip", "4b2f5edd2639b7470f034238b321d7002d8dfb4726d8558f52c17afac370eb2c", ("deno",), 40),),
    "linux-x86_64": (Artifact(f"{_DENO}/deno-x86_64-unknown-linux-gnu.zip", "e890975bc2549807bbcc0b584ffafda72cc7c93349dd99c80483dd784f6c4609", ("deno",), 40),),
    "linux-arm64": (Artifact(f"{_DENO}/deno-aarch64-unknown-linux-gnu.zip", "d49596c20b9788cf8f5d8ddf644103d4bde56ed239753f0bdb92ba9361d51905", ("deno",), 40),),
    "windows-x86_64": (Artifact(f"{_DENO}/deno-x86_64-pc-windows-msvc.zip", "cba84b26e0df5ae7f74fc66b86a95b866872a86292ebd84fa1e959927edd93bf", ("deno.exe",), 40),),
}

TOOLS = {"ffmpeg": FFMPEG, "deno": DENO}
_VERSION_ARGS = {"ffmpeg": "-version", "ffprobe": "-version", "deno": "--version"}


def platform_key() -> str:
    """Ex.: 'macos-arm64'. No Windows ARM usa o build x64 (roda por emulação)."""
    system = {"darwin": "macos", "win32": "windows"}.get(sys.platform, "linux")
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x86_64" if machine in ("x86_64", "amd64") else machine
    if system == "windows":
        arch = "x86_64"
    return f"{system}-{arch}"


def bin_dir() -> Path:
    return paths.subdir("bin")


def _exe(name: str) -> str:
    return name + (".exe" if sys.platform == "win32" else "")


def plan(tool: str) -> tuple[Artifact, ...]:
    key = platform_key()
    try:
        return TOOLS[tool][key]
    except KeyError:
        raise BaixaiError("unsupported_platform", f"Não há build verificado de {tool} para {key}. Instale-o manualmente e deixe-o no PATH.") from None


def installed(tool: str) -> bool:
    names = ("ffmpeg", "ffprobe") if tool == "ffmpeg" else (tool,)
    return all((bin_dir() / _exe(n)).is_file() for n in names)


def _download(art: Artifact, dest: Path, say: Callable[[str], None]) -> None:
    resp = safe_open(art.url, timeout=60, max_redirects=6)
    try:
        if resp.status != 200:
            raise BaixaiError("download_failed", f"O servidor respondeu HTTP {resp.status} para {art.url}")
        total = int(resp.headers.get("Content-Length") or 0)
        got, shown, h = 0, -1, hashlib.sha256()
        with dest.open("wb") as f:
            while True:
                chunk = resp.read(1 << 18)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                got += len(chunk)
                pct = int(got * 100 / total) // 10 * 10 if total else -1
                if pct != shown:
                    shown = pct
                    say(f"    {pct}%  ({got / 1e6:.0f} MB)" if pct >= 0 else f"    {got / 1e6:.0f} MB")
    finally:
        resp.close()
    if h.hexdigest() != art.sha256:
        dest.unlink(missing_ok=True)
        raise BaixaiError("checksum_mismatch", f"O SHA-256 de {art.url} não confere com o esperado; nada foi instalado.")


def _extract(zip_path: Path, wanted: tuple[str, ...], out_dir: Path) -> list[Path]:
    done: list[Path] = []
    with zipfile.ZipFile(zip_path) as z:
        by_base = {Path(i.filename).name: i for i in z.infolist() if not i.is_dir()}
        for name in wanted:
            info = by_base.get(name)
            if info is None:
                raise BaixaiError("bad_archive", f"{name} não está dentro do arquivo baixado.")
            target = out_dir / name  # só o nome-base: nunca usa o caminho de dentro do ZIP
            tmp = out_dir / (name + ".part")
            with z.open(info) as src, tmp.open("wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
            tmp.chmod(0o755)
            os.replace(tmp, target)
            done.append(target)
    return done


def _check_runs(exe: Path) -> str:
    base = exe.stem
    try:
        out = subprocess.run([str(exe), _VERSION_ARGS[base]], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError) as e:
        raise BaixaiError("install_failed", f"{exe.name} foi instalado, mas não executou: {e}") from e
    text = (out.stdout or out.stderr).strip().splitlines()
    if out.returncode != 0 or not text:
        raise BaixaiError("install_failed", f"{exe.name} foi instalado, mas retornou erro ao executar.")
    return text[0]


def install(tool: str, say: Callable[[str], None] = print, force: bool = False) -> dict:
    """Baixa, confere o SHA-256, extrai em <dados>/bin e testa a execução. Retorna {'tool', 'files', 'version'}."""
    if tool not in TOOLS:
        raise BaixaiError("invalid_option", f"Ferramenta desconhecida: {tool}")
    arts = plan(tool)
    out_dir = bin_dir()
    if installed(tool) and not force:
        say(f"{tool}: já instalado em {out_dir}")
    else:
        tmp_dir = paths.subdir("downloads-tmp")
        for art in arts:
            say(f"==> Baixando {Path(art.url).name} (~{art.size_mb} MB) de {art.url.split('/')[2]}")
            zpath = tmp_dir / f"{tool}-{art.sha256[:12]}.zip"
            try:
                _download(art, zpath, say)
                say("    SHA-256 conferido; extraindo")
                _extract(zpath, art.wanted, out_dir)
            finally:
                zpath.unlink(missing_ok=True)
    files = [out_dir / _exe(n) for n in (("ffmpeg", "ffprobe") if tool == "ffmpeg" else (tool,))]
    version = _check_runs(files[0])
    for extra in files[1:]:
        _check_runs(extra)
    say(f"    ok: {version}")
    return {"tool": tool, "files": [str(f) for f in files], "version": version}
