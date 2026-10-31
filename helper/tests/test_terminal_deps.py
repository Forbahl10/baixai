"""Uso pelo terminal (comando implícito, escolhas de modo) e instalador verificado de FFmpeg/Deno."""
import hashlib
import io
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from baixai_helper import cli, deps, terminal
from baixai_helper.errors import BaixaiError


def args(**kw):
    base = dict(audio=False, imagem=False, qualidade=None, pasta=None, bitrate=None, original=False, formato_imagem=None, tudo=False, itens=None, detalhes=False)
    return SimpleNamespace(**{**base, **kw})


class FakeSvc:
    def __init__(self, analysis):
        self._a = {"defaults": {"default_height": 1080, "default_mp3_bitrate": 192, "default_image_format": "original"}, "warnings": [], **analysis}

    def analyze(self, url):
        return {"url": url, "title": "Titulo", **self._a}


# ---------------------------------------------------------------- comando implícito
def test_link_sem_subcomando_vira_baixar(monkeypatch):
    got = {}
    monkeypatch.setattr(terminal, "run", lambda a: got.setdefault("a", a) and 0)
    assert cli.main(["-a", "https://example.com/x"]) == 0
    assert got["a"].audio and got["a"].urls == ["https://example.com/x"]
    got.clear()
    assert cli.main(["https://example.com/x", "https://example.com/y", "-q", "720"]) == 0
    assert got["a"].qualidade == 720 and len(got["a"].urls) == 2


def test_sem_argumentos_mostra_ajuda(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert 'baixai "LINK"' in out and "aspas" in out


def test_subcomandos_continuam_funcionando(monkeypatch, capsys):
    assert cli.main(["queue"]) == 0


# ---------------------------------------------------------------- escolha de modo e opções
def test_padrao_e_video_mp4_ate_1080():
    (url, mode, opts, _), = terminal.plan(FakeSvc({"modes": ["video", "audio"]}), "https://v/1", args())
    assert (mode, opts) == ("video", {"height": 1080, "container": "mp4"})


def test_qualidade_e_original():
    (_, mode, opts, _), = terminal.plan(FakeSvc({"modes": ["video", "audio"]}), "https://v/1", args(qualidade=720, original=True))
    assert opts == {"height": 720, "container": "original"}


def test_audio_mp3_com_bitrate():
    (_, mode, opts, _), = terminal.plan(FakeSvc({"modes": ["video", "audio"]}), "https://v/1", args(audio=True, bitrate=320))
    assert (mode, opts) == ("audio", {"audio_format": "mp3", "mp3_bitrate": 320})


def test_link_so_de_audio_escolhe_audio():
    (_, mode, _, _), = terminal.plan(FakeSvc({"modes": ["audio"]}), "https://s/1", args())
    assert mode == "audio"


def test_modo_indisponivel_explica_o_que_existe():
    with pytest.raises(BaixaiError) as e:
        terminal.plan(FakeSvc({"modes": ["image"]}), "https://i/1", args(audio=True))
    assert "áudio" in e.value.message and "imagem" in e.value.message


def test_imagem_com_conversao_e_itens():
    a = {"modes": ["image"], "image": {"items": [{}, {}, {}]}}
    (_, mode, opts, _), = terminal.plan(FakeSvc(a), "https://g/1", args(formato_imagem="png", itens="1,3"))
    assert mode == "image" and opts == {"image_format": "png", "items": [1, 3]}


def test_lista_sem_tty_exige_tudo_ou_itens(monkeypatch):
    monkeypatch.setattr(terminal.sys.stdin, "isatty", lambda: False, raising=False)
    entries = [{"index": i, "url": f"https://v/{i}", "title": f"T{i}"} for i in range(1, 4)]
    svc = FakeSvc({"modes": ["video", "audio"], "entries": entries})
    with pytest.raises(BaixaiError) as e:
        terminal.plan(svc, "https://v/list", args())
    assert e.value.code == "needs_confirmation" and "--tudo" in e.value.message
    assert [p[0] for p in terminal.plan(svc, "https://v/list", args(tudo=True))] == [f"https://v/{i}" for i in (1, 2, 3)]
    assert [p[0] for p in terminal.plan(svc, "https://v/list", args(itens="2"))] == ["https://v/2"]
    with pytest.raises(BaixaiError):
        terminal.plan(svc, "https://v/list", args(itens="9"))


def test_itens_invalidos():
    with pytest.raises(BaixaiError):
        terminal.plan(FakeSvc({"modes": ["image"], "image": {"items": [{}]}}), "https://g/1", args(itens="a,b"))


# ---------------------------------------------------------------- instalador de FFmpeg/Deno
def test_tabelas_cobrem_todas_as_plataformas_com_sha256():
    keys = {"macos-arm64", "macos-x86_64", "linux-x86_64", "linux-arm64", "windows-x86_64"}
    for table in (deps.FFMPEG, deps.DENO):
        assert set(table) == keys
        for arts in table.values():
            for a in arts:
                assert a.url.startswith("https://") and len(a.sha256) == 64 and set(a.sha256) <= set("0123456789abcdef")


@pytest.mark.parametrize("platform_, machine, want", [
    ("darwin", "arm64", "macos-arm64"), ("darwin", "x86_64", "macos-x86_64"), ("linux", "x86_64", "linux-x86_64"),
    ("linux", "aarch64", "linux-arm64"), ("win32", "AMD64", "windows-x86_64"), ("win32", "ARM64", "windows-x86_64"),
])
def test_platform_key(monkeypatch, platform_, machine, want):
    monkeypatch.setattr(deps.sys, "platform", platform_)
    monkeypatch.setattr(deps.platform, "machine", lambda: machine)
    assert deps.platform_key() == want


def test_plataforma_sem_build_verificado(monkeypatch):
    monkeypatch.setattr(deps, "platform_key", lambda: "linux-riscv64")
    with pytest.raises(BaixaiError) as e:
        deps.plan("ffmpeg")
    assert e.value.code == "unsupported_platform"


def make_zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_extracao_usa_so_o_nome_base_e_ignora_caminhos(tmp_path):
    z = tmp_path / "a.zip"
    z.write_bytes(make_zip({"../../escape/ffmpeg": b"BIN", "pasta/outro.txt": b"x"}))
    out = tmp_path / "bin"; out.mkdir()
    (done,) = deps._extract(z, ("ffmpeg",), out)
    assert done == out / "ffmpeg" and done.read_bytes() == b"BIN"
    assert not (tmp_path.parent / "escape").exists() and sorted(p.name for p in out.iterdir()) == ["ffmpeg"]


def test_extracao_de_arquivo_ausente_falha(tmp_path):
    z = tmp_path / "a.zip"; z.write_bytes(make_zip({"x": b"1"}))
    with pytest.raises(BaixaiError):
        deps._extract(z, ("ffmpeg",), tmp_path)


class Serve:
    def __init__(self, body: bytes):
        outer = body

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.send_header("Content-Length", str(len(outer))); self.end_headers(); self.wfile.write(outer)

            def log_message(self, *a): pass

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/f.zip"

    def close(self): self.srv.shutdown()


def test_download_confere_sha256(tmp_path, monkeypatch):
    monkeypatch.setenv("BAIXAI_ALLOW_PRIVATE_NETWORK", "1")
    body = make_zip({"ffmpeg": b"BIN"})
    s = Serve(body)
    try:
        good = deps.Artifact(s.url, hashlib.sha256(body).hexdigest(), ("ffmpeg",), 1)
        dest = tmp_path / "ok.zip"
        deps._download(good, dest, lambda m: None)
        assert dest.read_bytes() == body
        bad = deps.Artifact(s.url, "0" * 64, ("ffmpeg",), 1)
        dest2 = tmp_path / "bad.zip"
        with pytest.raises(BaixaiError) as e:
            deps._download(bad, dest2, lambda m: None)
        assert e.value.code == "checksum_mismatch" and not dest2.exists()
    finally:
        s.close()
