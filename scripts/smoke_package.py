"""Teste de fumaça do PACOTE final em um sistema real (macOS, Linux ou Windows).

Uso: python scripts/smoke_package.py <pasta-do-pacote-extraído>
Instala com o instalador do pacote (HOME/APPDATA isolados), simula o Chrome lançando o host a partir do manifesto,
faz um download + conversão reais de uma imagem servida localmente e desinstala.
"""
from __future__ import annotations

import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WIN = sys.platform == "win32"
pkg = Path(sys.argv[1]).resolve()
tmp = Path(tempfile.mkdtemp(prefix="baixai-smoke-"))
home = tmp / "home"
home.mkdir()
env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "APPDATA": str(home / "AppData" / "Roaming"), "LOCALAPPDATA": str(home / "AppData" / "Local"),
       "XDG_DATA_HOME": str(home / ".local" / "share")}
(home / "AppData" / "Roaming").mkdir(parents=True)
(home / "AppData" / "Local").mkdir(parents=True)


def step(msg: str) -> None:
    print(f"\n=== {msg}", flush=True)


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("+", " ".join(map(str, cmd)), flush=True)
    r = subprocess.run(cmd, env=env, text=True, capture_output=True, **kw)
    print(r.stdout[-1500:], r.stderr[-800:], sep="\n")
    if r.returncode != 0:
        raise SystemExit(f"FALHOU (código {r.returncode}): {' '.join(map(str, cmd))}")
    return r


def manifest_path() -> Path:
    if WIN:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\NativeMessagingHosts\local.baixai.helper") as k:
            return Path(winreg.QueryValueEx(k, "")[0])
    base = home / ("Library/Application Support/Google/Chrome" if sys.platform == "darwin" else ".config/google-chrome")
    return base / "NativeMessagingHosts" / "local.baixai.helper.json"


# ---------------------------------------------------------------- 1. instalar
step("instalação pelo instalador do pacote")
if WIN:
    sh(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(pkg / "install.ps1"), "-NoFfmpeg"])
else:
    sh([str(pkg / "install.sh"), "--no-ffmpeg"])
mp = manifest_path()
manifest = json.loads(mp.read_text(encoding="utf-8"))
print("manifesto:", json.dumps(manifest, indent=1))
assert manifest["name"] == "local.baixai.helper" and manifest["type"] == "stdio"
assert Path(manifest["path"]).is_absolute() and Path(manifest["path"]).is_file(), "o manifesto aponta para um executável inexistente"
assert manifest["allowed_origins"] and all(o.startswith("chrome-extension://") and o.endswith("/") for o in manifest["allowed_origins"])

# ---------------------------------------------------------------- 2. mídia local para baixar
from PIL import Image  # noqa: E402  (disponível no ambiente da CI)

buf = io.BytesIO()
Image.new("RGBA", (16, 16), (0, 120, 255, 0)).save(buf, "PNG")
PNG = buf.getvalue()


class H(BaseHTTPRequestHandler):
    def do_HEAD(self): self._go(True)
    def do_GET(self): self._go(False)
    def _go(self, head):
        self.send_response(200); self.send_header("Content-Type", "image/png"); self.send_header("Content-Length", str(len(PNG))); self.end_headers()
        if not head: self.wfile.write(PNG)
    def log_message(self, *a): pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/figura.png"

# ---------------------------------------------------------------- 3. simular o Chrome
step("simulando o Chrome: lança o host com a origem da extensão (e --parent-window no Windows)")
origin = manifest["allowed_origins"][0]
argv = [manifest["path"], origin] + (["--parent-window=0"] if WIN else [])
host_env = {**env, "BAIXAI_ALLOW_PRIVATE_NETWORK": "1"}  # só para o servidor de teste em 127.0.0.1
p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=host_env)
events: list[dict] = []
lock = threading.Condition()
resp: dict = {}


def reader():
    while True:
        h = p.stdout.read(4)
        if len(h) < 4:
            return
        body = p.stdout.read(struct.unpack("=I", h)[0])
        m = json.loads(body)
        with lock:
            (resp.__setitem__(m["id"], m) if "ok" in m else events.append(m))
            lock.notify_all()


threading.Thread(target=reader, daemon=True).start()


def call(cmd: str, payload: dict | None = None, timeout=60) -> dict:
    mid = f"s{len(resp)}"
    b = json.dumps({"id": mid, "cmd": cmd, "payload": payload or {}}).encode()
    p.stdin.write(struct.pack("=I", len(b)) + b); p.stdin.flush()
    with lock:
        assert lock.wait_for(lambda: mid in resp, timeout), f"sem resposta para {cmd}"
    return resp[mid]


r = call("hello")
assert r["ok"], r
d = r["data"]
print("hello:", d["version"], "protocolo", d["protocol"], d["platform"])
assert d["tools"]["ytdlp"]["ok"] and d["tools"]["gallerydl"]["ok"], d["tools"]
print("yt-dlp", d["tools"]["ytdlp"]["version"], "| gallery-dl", d["tools"]["gallerydl"]["version"], "| ffmpeg", d["tools"]["ffmpeg"]["ok"])
assert call("analyze", {"url": "file:///etc/passwd"})["error"]["code"] == "invalid_scheme"

step("fluxo real com o executável empacotado: analisar → enfileirar → baixar → converter PNG→JPEG (Pillow embutido)")
dl = tmp / "Downloads"
assert call("set_settings", {"settings": {"download_dir": str(dl)}})["ok"]
a = call("analyze", {"url": url})
assert a["ok"] and a["data"]["modes"] == ["image"], a
e = call("enqueue", {"url": url, "mode": "image", "options": {"image_format": "jpeg", "engine": "direct"}})
assert e["ok"], e
jid = e["data"]["job"]["id"]
end = time.time() + 60
job = None
while time.time() < end:
    with lock:
        for ev in events:
            if ev.get("event") == "job" and ev["job"]["id"] == jid and ev["job"]["state"] in ("done", "failed"):
                job = ev["job"]
        if job:
            break
        lock.wait(0.5)
assert job and job["state"] == "done", job
f = Path(job["files"][0]["path"])
assert f.suffix == ".jpg" and f.is_file() and Image.open(f).format == "JPEG", f
assert any("transparência" in n for n in job["notes"]), job["notes"]
print("arquivo:", f, f.stat().st_size, "bytes")

step("origem não autorizada deve ser recusada")
bad = subprocess.run([manifest["path"], "chrome-extension://" + "z" * 32 + "/"], stdin=subprocess.DEVNULL, capture_output=True, env=host_env, timeout=30)
assert bad.returncode == 2 and b"origin_not_allowed" in bad.stdout, (bad.returncode, bad.stdout[:200])

p.stdin.close()
assert p.wait(30) == 0

# ---------------------------------------------------------------- 4. desinstalar
step("desinstalação")
if WIN:
    sh(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(pkg / "uninstall.ps1"), "-PurgeData"])
else:
    sh([str(pkg / "uninstall.sh"), "--purge-data"])
assert not mp.exists(), "o manifesto deveria ter sido removido"
if WIN:
    import winreg

    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\NativeMessagingHosts\local.baixai.helper")
        raise SystemExit("a chave do registro deveria ter sido removida")
    except FileNotFoundError:
        pass
print("\nSMOKE OK")
