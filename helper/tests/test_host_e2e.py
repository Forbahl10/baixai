"""Host real em subprocesso, falando o protocolo Native Messaging.

O download usa um servidor HTTP local servindo uma imagem verdadeira (rota 'Link direto'),
sem simular o mecanismo de download. Plataformas reais ficam em test_live.py.
"""
import io
import json
import os
import struct
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import Image

EXT_ID = "abcdefghijklmnopabcdefghijklmnop"


def png_bytes():
    b = io.BytesIO()
    Image.new("RGBA", (8, 8), (0, 128, 255, 0)).save(b, "PNG")
    return b.getvalue()


class Media(BaseHTTPRequestHandler):
    def do_HEAD(self): self._serve(head=True)
    def do_GET(self): self._serve()
    def _serve(self, head=False):
        if self.path.startswith("/redir"):
            self.send_response(302); self.send_header("Location", "/img/figura.png"); self.end_headers(); return
        if self.path.startswith("/img/"):
            data = png_bytes()
            self.send_response(200); self.send_header("Content-Type", "image/png"); self.send_header("Content-Length", str(len(data))); self.end_headers()
            if not head: self.wfile.write(data)
            return
        if self.path.startswith("/tom.wav"):
            import math, wave
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
                w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 8))) for i in range(8000)))
            data = buf.getvalue()
            self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("Content-Length", str(len(data))); self.end_headers()
            if not head: self.wfile.write(data)
            return
        if self.path.startswith("/slow.mp3"):
            self.send_response(200); self.send_header("Content-Type", "audio/mpeg"); self.send_header("Content-Length", "100000000"); self.end_headers()
            try:
                for _ in range(1000):
                    if head: break
                    self.wfile.write(b"\0" * 1000); self.wfile.flush(); time.sleep(0.02)
            except OSError:
                pass
            return
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(b"<html>")
    def log_message(self, *a): pass


@pytest.fixture
def media_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Media)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


class HostProc:
    def __init__(self, tmp_path, origin=f"chrome-extension://{EXT_ID}/", ids=EXT_ID, private=True):
        env = {**os.environ, "BAIXAI_TOOLS_PATH": os.environ.get("BAIXAI_TOOLS_PATH", ""), "BAIXAI_DATA_DIR": str(tmp_path / "data"), "BAIXAI_ALLOWED_IDS": ids, "PYTHONPATH": ""}
        if private:
            env["BAIXAI_ALLOW_PRIVATE_NETWORK"] = "1"
        self.p = subprocess.Popen([sys.executable, "-I", "-m", "baixai_helper", origin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.events, self.responses, self._cv = [], {}, threading.Condition()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        while True:
            h = self.p.stdout.read(4)
            if len(h) < 4:
                break
            (n,) = struct.unpack("=I", h)
            msg = json.loads(self.p.stdout.read(n))
            with self._cv:
                (self.responses.__setitem__(msg["id"], msg) if "ok" in msg else self.events.append(msg))
                self._cv.notify_all()

    def send(self, cmd, payload=None, mid=None, raw=None):
        if raw is None:
            raw = json.dumps({"id": mid, "cmd": cmd, "payload": payload or {}}).encode()
        self.p.stdin.write(struct.pack("=I", len(raw)) + raw); self.p.stdin.flush()

    def call(self, cmd, payload=None, timeout=20):
        mid = f"r{len(self.responses)}{time.time_ns() % 10**6}"
        self.send(cmd, payload, mid)
        with self._cv:
            assert self._cv.wait_for(lambda: mid in self.responses, timeout), f"sem resposta para {cmd}"
        return self.responses[mid]

    def wait_event(self, pred, timeout=30):
        with self._cv:
            assert self._cv.wait_for(lambda: any(pred(e) for e in self.events), timeout), "evento não chegou"
            return next(e for e in self.events if pred(e))

    def close(self):
        try: self.p.stdin.close()
        except OSError: pass
        try: self.p.wait(15)
        except subprocess.TimeoutExpired: self.p.kill()


@pytest.fixture
def host(tmp_path):
    h = HostProc(tmp_path)
    yield h
    h.close()


def test_hello_e_diagnostico(host, tmp_path):
    r = host.call("hello")
    assert r["ok"] and r["data"]["protocol"] == 1 and r["data"]["version"] and "ytdlp" in r["data"]["tools"]
    assert os.path.isabs(r["data"]["download_dir"])


def test_origem_nao_autorizada_e_recusada(tmp_path):
    h = HostProc(tmp_path, origin="chrome-extension://" + "z" * 32 + "/")
    h.p.wait(15)
    assert h.p.returncode == 2
    h2 = HostProc(tmp_path, origin="https://evil.example/")
    h2.p.wait(15)
    assert h2.p.returncode == 2


def test_mensagens_invalidas_recebem_erro_estruturado(host):
    assert host.call("analyze", {"url": 5})["error"]["code"] == "invalid_payload"
    host.send("x", raw=b"isto nao e json")
    host.send("hello", mid="ok1")
    with host._cv:
        host._cv.wait_for(lambda: "ok1" in host.responses, 10)
    assert host.responses["ok1"]["ok"]  # o host continua vivo e alinhado
    assert host.call("analyze", {"url": "ftp://x.com/a"})["error"]["code"] == "invalid_scheme"


def test_fluxo_completo_imagem_direta_com_conversao(host, media_server, tmp_path):
    dl = tmp_path / "Downloads"
    assert host.call("set_settings", {"settings": {"download_dir": str(dl)}})["ok"]
    url = f"{media_server}/redir"  # inclui redirecionamento
    a = host.call("analyze", {"url": url})
    assert a["ok"] and a["data"]["modes"] == ["image"] and a["data"]["engine"] == "direct"
    assert "transparência" in a["data"]["image"]["note"]
    e = host.call("enqueue", {"url": url, "mode": "image", "options": {"image_format": "jpeg"}, "meta": {"title": "figura"}})
    assert e["ok"], e
    jid = e["data"]["job"]["id"]
    done = host.wait_event(lambda ev: ev.get("event") == "job" and ev["job"]["id"] == jid and ev["job"]["state"] == "done")["job"]
    assert any("transparência" in n for n in done["notes"])
    path = done["files"][0]["path"]
    assert path.endswith(".jpg") and os.path.dirname(path).startswith(str(dl)) and Image.open(path).format == "JPEG"
    states = [ev["job"]["state"] for ev in host.events if ev.get("event") == "job" and ev["job"]["id"] == jid]
    assert states[0] == "waiting" and "downloading" in states
    # duplicação
    again = host.call("enqueue", {"url": url, "mode": "image", "options": {"image_format": "jpeg"}})
    assert again["data"]["duplicate"] == "done"
    assert host.call("list_jobs")["data"]["jobs"][0]["state"] == "done"


def test_cancelamento_pelo_protocolo(host, media_server, tmp_path):
    host.call("set_settings", {"settings": {"download_dir": str(tmp_path / "dl")}})
    e = host.call("enqueue", {"url": f"{media_server}/slow.mp3", "mode": "audio", "options": {"audio_format": "original"}})
    jid = e["data"]["job"]["id"]
    host.wait_event(lambda ev: ev.get("event") == "job" and ev["job"]["id"] == jid and ev["job"]["state"] == "downloading")
    assert host.call("cancel", {"id": jid})["ok"]
    host.wait_event(lambda ev: ev.get("event") == "job" and ev["job"]["id"] == jid and ev["job"]["state"] == "cancelled")
    assert not list((tmp_path / "dl").rglob("*.part"))


def test_fila_sobrevive_ao_reinicio_do_host(media_server, tmp_path):
    h = HostProc(tmp_path)
    h.call("set_settings", {"settings": {"download_dir": str(tmp_path / "dl")}})
    e = h.call("enqueue", {"url": f"{media_server}/slow.mp3", "mode": "audio", "options": {"audio_format": "original"}})
    jid = e["data"]["job"]["id"]
    h.wait_event(lambda ev: ev.get("event") == "job" and ev["job"]["id"] == jid and ev["job"]["state"] == "downloading")
    h.p.kill()  # morte abrupta (como fechar o Chrome à força)
    h.p.wait()
    h2 = HostProc(tmp_path)
    jobs = h2.call("list_jobs")["data"]["jobs"]
    assert [j["id"] for j in jobs] == [jid]
    h2.wait_event(lambda ev: ev.get("event") == "job" and ev["job"]["id"] == jid and ev["job"]["state"] in ("analyzing", "downloading"))
    h2.close()


def test_rede_local_bloqueada_sem_a_variavel_de_teste(tmp_path, media_server):
    h = HostProc(tmp_path, private=False)
    r = h.call("analyze", {"url": f"{media_server}/img/a.png"})
    assert not r["ok"] and r["error"]["code"] in ("blocked_port", "blocked_host")
    r = h.call("analyze", {"url": "http://169.254.169.254/latest/meta-data/"})
    assert r["error"]["code"] in ("blocked_port", "blocked_host", "invalid_scheme") or not r["ok"]
    h.close()


@pytest.mark.skipif(not (__import__("shutil").which("ffmpeg") or os.environ.get("BAIXAI_FFMPEG")), reason="FFmpeg não encontrado")
def test_audio_direto_convertido_para_mp3_com_ffmpeg(host, media_server, tmp_path):
    host.call("set_settings", {"settings": {"download_dir": str(tmp_path / "dl")}})
    url = f"{media_server}/tom.wav"
    a = host.call("analyze", {"url": url})
    assert a["data"]["modes"] == ["audio"]
    e = host.call("enqueue", {"url": url, "mode": "audio", "options": {"audio_format": "mp3", "mp3_bitrate": 128}})
    jid = e["data"]["job"]["id"]
    done = host.wait_event(lambda ev: ev.get("event") == "job" and ev["job"]["id"] == jid and ev["job"]["state"] in ("done", "failed"))["job"]
    assert done["state"] == "done", done.get("error")
    path = done["files"][0]["path"]
    assert path.endswith(".mp3") and open(path, "rb").read(3) in (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
    assert not list((tmp_path / "dl").rglob("*.wav"))
