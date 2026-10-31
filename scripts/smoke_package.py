"""Teste de fumaça do PACOTE final, do jeito que o usuário usa (macOS, Linux e Windows).

Uso: python scripts/smoke_package.py <pasta-dist-com-o-pacote>

Faz, num HOME/APPDATA isolado:
  1. serve o pacote como se fosse uma Release do GitHub e roda get.sh / get.ps1 de verdade (com --deps: baixa FFmpeg e Deno reais);
  2. usa o comando `baixai` instalado: --version, doctor, os motores embutidos (yt-dlp e gallery-dl);
  3. baixa por link um áudio e uma imagem servidos localmente, convertendo (WAV->MP3 e PNG->JPEG) com o FFmpeg instalado;
  4. confere que links perigosos são recusados;
  5. desinstala e confere que nada ficou.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")

WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"
ROOT = Path(__file__).resolve().parent.parent
dist = Path(sys.argv[1]).resolve()

tmp = Path(tempfile.mkdtemp(prefix="baixai-smoke-"))
home = tmp / "home"
(home / "AppData" / "Roaming").mkdir(parents=True)
(home / "AppData" / "Local").mkdir(parents=True)
(home / ".local" / "share").mkdir(parents=True)
env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "APPDATA": str(home / "AppData" / "Roaming"),
       "LOCALAPPDATA": str(home / "AppData" / "Local"), "XDG_DATA_HOME": str(home / ".local" / "share"),
       "PYTHONIOENCODING": "utf-8", "BAIXAI_ALLOW_PRIVATE_NETWORK": "1", "SHELL": "/bin/sh"}
env.pop("BAIXAI_DATA_DIR", None)
env.pop("PSModulePath", None)  # o Windows PowerShell 5.1 não deve herdar o do pwsh 7 (o passo da CI roda em pwsh)

if WIN:
    app_root = home / "AppData" / "Roaming" / "Baixai"
    cmd_path = app_root / "cmd" / "baixai.cmd"
    exe = app_root / "app" / "baixai-helper" / "baixai-helper.exe"
    uninstaller = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(app_root / "desinstalar.ps1"), "-PurgeData"]
elif MAC:
    app_root = home / "Library" / "Application Support" / "Baixai"
    cmd_path = home / ".local" / "bin" / "baixai"
    exe = app_root / "app" / "baixai-helper" / "baixai-helper"
    uninstaller = [str(app_root / "desinstalar.sh"), "--purge-data"]
else:
    app_root = home / ".local" / "share" / "baixai"
    cmd_path = home / ".local" / "bin" / "baixai"
    exe = app_root / "app" / "baixai-helper" / "baixai-helper"
    uninstaller = [str(app_root / "desinstalar.sh"), "--purge-data"]


def step(msg: str) -> None:
    print(f"\n=== {msg}", flush=True)


def run(cmd: list[str], timeout=900, ok=(0,), **kw) -> subprocess.CompletedProcess:
    print("+", " ".join(map(str, cmd)), flush=True)
    r = subprocess.run(cmd, env={**env, **kw.pop("extra_env", {})}, text=True, encoding="utf-8", errors="replace",
                       capture_output=True, timeout=timeout, **kw)
    print((r.stdout or "")[-2500:], (r.stderr or "")[-1500:], sep="\n", flush=True)
    if r.returncode not in ok:
        raise SystemExit(f"FALHOU (código {r.returncode}): {' '.join(map(str, cmd))}")
    return r


def serve(directory: Path) -> tuple[ThreadingHTTPServer, str]:
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a): pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(directory)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


# ------------------------------------------------------------------ 1. simular a Release e instalar com get.sh / get.ps1
step("Release simulada (pacote real + SHA256SUMS) servida localmente")
version = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
pkgs = [p for p in dist.glob("baixai-helper-*") if p.suffix == ".zip" or p.name.endswith(".tar.gz")]
assert len(pkgs) == 1, f"esperava 1 pacote do helper em {dist}, achei {pkgs}"
rel = tmp / "rel" / "download" / f"v{version}"
rel.mkdir(parents=True)
shutil.copy2(pkgs[0], rel / pkgs[0].name)
(rel / "SHA256SUMS.txt").write_text(f"{hashlib.sha256(pkgs[0].read_bytes()).hexdigest()}  {pkgs[0].name}\n")
rel_srv, rel_url = serve(tmp / "rel")
install_env = {"BAIXAI_BASE_URL": rel_url, "BAIXAI_VERSION": version}

step("get.sh / get.ps1 (instala, baixa FFmpeg e Deno reais, confere SHA-256)")
if WIN:
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "get.ps1")], extra_env={**install_env, "BAIXAI_INSTALL_OPTIONS": "Deps,NoPath"})
else:
    run(["sh", str(ROOT / "get.sh"), "--deps", "--no-path"], extra_env=install_env)
assert cmd_path.is_file() and exe.is_file(), "o comando baixai ou o aplicativo não foram instalados"

step("integridade: pacote adulterado deve ser recusado antes de instalar")
(rel / "SHA256SUMS.txt").write_text(f"{'0' * 64}  {pkgs[0].name}\n")
bad_home = tmp / "bad"
bad_home.mkdir()
bad = run(["sh", str(ROOT / "get.sh"), "--no-deps", "--no-path"] if not WIN else
          ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "get.ps1")],
          extra_env={**install_env, "HOME": str(bad_home), "APPDATA": str(bad_home), "XDG_DATA_HOME": str(bad_home), "LOCALAPPDATA": str(bad_home)}, ok=(1, 2, 255) if not WIN else (0, 1, 255))
out_bad = bad.stdout + bad.stderr  # sem acento: o console do Windows pode trocar a codificação
assert "SHA-256" in out_bad and "confere" in out_bad, "esperava a mensagem de SHA-256 inválido"
assert not any(bad_home.iterdir()), "nada deveria ter sido instalado"
(rel / "SHA256SUMS.txt").write_text(f"{hashlib.sha256(pkgs[0].read_bytes()).hexdigest()}  {pkgs[0].name}\n")
rel_srv.shutdown()

# ------------------------------------------------------------------ 2. o comando instalado
baixai = [str(cmd_path)]
step("baixai --version / doctor / motores embutidos")
assert version in run(baixai + ["--version"]).stdout
doc = run(baixai + ["doctor"]).stdout
for needle in ("[ok] yt-dlp", "[ok] gallery-dl", "[ok] FFmpeg", "[ok] Runtime JS"):
    assert needle in doc, f"doctor não mostrou '{needle}'"
assert run([str(exe), "--engine", "yt-dlp", "--version"]).stdout.strip()
assert run([str(exe), "--engine", "gallery-dl", "--version"]).stdout.strip()

# ------------------------------------------------------------------ 3. downloads reais de mídia local
bin_dir = app_root / "bin"
ffmpeg, ffprobe = bin_dir / ("ffmpeg.exe" if WIN else "ffmpeg"), bin_dir / ("ffprobe.exe" if WIN else "ffprobe")
assert ffmpeg.is_file() and ffprobe.is_file()
media = tmp / "media"
media.mkdir()
run([str(ffmpeg), "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-y", str(media / "tom.wav")])
run([str(ffmpeg), "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=1", "-frames:v", "1", "-y", str(media / "figura.png")])
media_srv, media_url = serve(media)
dest = tmp / "Downloads"


def codec(path: Path) -> str:
    return run([str(ffprobe), "-v", "error", "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1", str(path)]).stdout.strip()


step("baixai LINK (áudio detectado sozinho) -> MP3")
r = run(baixai + [f"{media_url}/tom.wav", "-o", str(dest)])
mp3 = next(dest.rglob("*.mp3"))
assert codec(mp3) == "mp3", f"esperava MP3, veio {codec(mp3)}"
assert "Pronto" in r.stdout

step("baixai -i LINK --formato-imagem jpeg -> JPEG")
run(baixai + ["-i", f"{media_url}/figura.png", "--formato-imagem", "jpeg", "-o", str(dest)])
jpg = next(dest.rglob("*.jpg"))
assert codec(jpg) == "mjpeg", f"esperava JPEG, veio {codec(jpg)}"

step("links perigosos e opções inválidas são recusados")
for bad_url in ("file:///etc/passwd", "ftp://example.com/x", "http://localhost:22/", "http://169.254.169.254/latest/meta-data/"):
    r = run(baixai + [bad_url], ok=(1,), extra_env={"BAIXAI_ALLOW_PRIVATE_NETWORK": ""})
    assert "Erro" in r.stderr, f"{bad_url}: esperava mensagem de erro"
run(baixai + ["-a", f"{media_url}/figura.png"], ok=(1,))
media_srv.shutdown()

# ------------------------------------------------------------------ 4. desinstalar
step("desinstalação")
run(uninstaller)
assert not cmd_path.exists(), "o comando baixai deveria ter sido removido"
assert not app_root.exists(), "a pasta do Baixaí deveria ter sido removida (--purge-data)"
print("\nSMOKE OK")
shutil.rmtree(tmp, ignore_errors=True)
