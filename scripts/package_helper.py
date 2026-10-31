"""Empacota o aplicativo auxiliar (PyInstaller) para o sistema atual. Funciona em macOS, Linux e Windows.

Saída em dist/: baixai-helper-<versão>-<so>-<arquitetura>.(tar.gz|zip). Com --source também gera o tarball do código-fonte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST, BUILD = ROOT / "dist", ROOT / "build"


def version() -> str:
    return json.loads((ROOT / "package.json").read_text())["version"]


def target() -> tuple[str, str]:
    os_name = {"darwin": "macos", "win32": "windows"}.get(sys.platform, "linux")
    arch = {"aarch64": "arm64", "amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64"}.get(platform.machine().lower(), platform.machine().lower())
    return os_name, arch


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def build_exe() -> Path:
    for d in (BUILD / "helper-dist", BUILD / "pyi-work"):
        shutil.rmtree(d, ignore_errors=True)
    (BUILD / "pyi").mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "baixai-helper",
         "--distpath", str(BUILD / "helper-dist"), "--workpath", str(BUILD / "pyi-work"), "--specpath", str(BUILD / "pyi"),
         "--collect-submodules", "gallery_dl", "--collect-submodules", "yt_dlp", "--collect-all", "yt_dlp_ejs",
         "--copy-metadata", "yt-dlp", "--copy-metadata", "gallery-dl", "--copy-metadata", "baixai-helper",
         "--hidden-import", "PIL.Image", "--exclude-module", "tkinter", str(ROOT / "helper" / "entry.py")])
    return BUILD / "helper-dist" / "baixai-helper"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", action="store_true", help="gera também o tarball do código-fonte")
    ap.add_argument("--skip-inventory", action="store_true")
    args = ap.parse_args()
    ver, (os_name, arch) = version(), target()
    name = f"baixai-helper-{ver}-{os_name}-{arch}"
    DIST.mkdir(exist_ok=True)
    exe_dir = build_exe()
    if not args.skip_inventory:
        run([sys.executable, str(ROOT / "scripts" / "gen_inventory.py"), "--fetch-sources"])

    stage = BUILD / name
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    shutil.copytree(exe_dir, stage / "baixai-helper")
    for f in ("install.sh", "uninstall.sh", "install.ps1", "uninstall.ps1", "instalar.bat", "remover.bat", "LEIA-ME.txt", "CODIGO-FONTE.md"):
        shutil.copy2(ROOT / "packaging" / f, stage / f)
    for f in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / f, stage / f)
    if (DIST / "sources").is_dir():
        shutil.copytree(DIST / "sources", stage / "sources")
    dev_id = ROOT / "extension" / "dev-extension-id.txt"
    if dev_id.exists():
        shutil.copy2(dev_id, stage / "DEFAULT_EXTENSION_IDS")

    if os_name == "windows":
        out = DIST / f"{name}.zip"
        out.unlink(missing_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(stage.rglob("*")):
                if p.is_file():
                    z.write(p, Path(name) / p.relative_to(stage))
    else:
        out = DIST / f"{name}.tar.gz"
        with tarfile.open(out, "w:gz") as t:
            t.add(stage, arcname=name)  # preserva bits de execução (install.sh, binário)
    print("Pacote:", out, f"({out.stat().st_size / 1e6:.1f} MB)")

    if args.source:
        src = DIST / f"baixai-source-{ver}.tar.gz"
        skip = {".venv", ".tools", ".scratch", "node_modules", "build", "dist", "__pycache__", ".pytest_cache", ".git"}
        with tarfile.open(src, "w:gz") as t:
            t.add(ROOT, arcname=f"baixai-{ver}", filter=lambda ti: None if (set(Path(ti.name).parts) & skip or ti.name.endswith(".egg-info")) else ti)
        print("Fonte:", src)

    sums = sorted([*DIST.glob("*.tar.gz"), *DIST.glob("*.zip")])
    (DIST / "SHA256SUMS.txt").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in sums))
    print((DIST / "SHA256SUMS.txt").read_text())


if __name__ == "__main__":
    main()
