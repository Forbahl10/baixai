"""Integração REAL (rede + plataformas). Não rodam por padrão: `pytest -m live`.

Os links vêm de variáveis de ambiente para que cada pessoa teste com conteúdo próprio ou autorizado:
  BAIXAI_LIVE_YOUTUBE, BAIXAI_LIVE_X_IMAGE, BAIXAI_LIVE_SOUNDCLOUD, BAIXAI_LIVE_TIKTOK, BAIXAI_LIVE_INSTAGRAM
Requer yt-dlp, gallery-dl e FFmpeg disponíveis.
"""
import os

import pytest

from baixai_helper.service import Service

pytestmark = pytest.mark.live


def need(var):
    url = os.environ.get(var)
    if not url:
        pytest.skip(f"defina {var} com um link próprio/autorizado")
    return url


@pytest.fixture
def svc(tmp_path):
    s = Service()
    s.settings.update({"download_dir": str(tmp_path / "dl")})
    s.start()
    yield s
    s.shutdown()


def run(svc, url, mode, options):
    j = svc.queue.enqueue(url, mode, options, force=True)["job"]
    assert svc.queue.wait_idle(600)
    final = next(x for x in svc.queue.list() if x["id"] == j["id"])
    assert final["state"] == "done", final
    return final


def test_youtube_video_mp4_e_mp3(svc):
    url = need("BAIXAI_LIVE_YOUTUBE")
    a = svc.analyze(url)
    assert "video" in a["modes"] and a["video"]["formats"]
    smallest = a["video"]["formats"][-1]["height"]
    v = run(svc, url, "video", {"height": smallest, "container": "mp4"})
    assert v["files"][0]["path"].endswith(".mp4")
    m = run(svc, url, "audio", {"audio_format": "mp3", "mp3_bitrate": 128})
    assert m["files"][0]["path"].endswith(".mp3")


def test_x_imagem(svc):
    url = need("BAIXAI_LIVE_X_IMAGE")
    a = svc.analyze(url)
    assert a["modes"] == ["image"]
    run(svc, url, "image", {"image_format": "original"})


@pytest.mark.parametrize("var", ["BAIXAI_LIVE_SOUNDCLOUD", "BAIXAI_LIVE_TIKTOK", "BAIXAI_LIVE_INSTAGRAM"])
def test_analise_demais_plataformas(svc, var):
    a = svc.analyze(need(var))
    assert a["modes"]


def test_cancelamento_real_do_ytdlp_encerra_o_processo(svc, tmp_path):
    """Cancela um download real em andamento: o subprocesso deve morrer e a pasta temporária sumir."""
    import subprocess
    import time

    url = need("BAIXAI_LIVE_YOUTUBE")
    a = svc.analyze(url)
    biggest = a["video"]["formats"][0]["height"]
    j = svc.queue.enqueue(url, "video", {"height": biggest, "container": "mp4"}, force=True)["job"]
    end = time.time() + 120
    while time.time() < end:
        cur = next(x for x in svc.queue.list() if x["id"] == j["id"])
        if cur["state"] == "downloading" and (cur["progress"] or 0) > 0.0:
            break
        time.sleep(0.2)
    else:
        pytest.fail("o download não começou")
    svc.queue.cancel(j["id"])
    end = time.time() + 30
    while time.time() < end and next(x for x in svc.queue.list() if x["id"] == j["id"])["state"] != "cancelled":
        time.sleep(0.1)
    assert next(x for x in svc.queue.list() if x["id"] == j["id"])["state"] == "cancelled"
    time.sleep(0.5)
    left = subprocess.run(["pgrep", "-f", f"yt_dlp.*{url.split('v=')[-1]}"], capture_output=True, text=True).stdout.strip()
    assert left == "", f"processo yt-dlp ainda vivo: {left}"
    assert not (tmp_path / "dl" / ".baixai-tmp" / j["id"]).exists()


@pytest.mark.live
def test_spotify_musica_vira_mp3_do_youtube(tmp_path):
    """BAIXAI_LIVE_SPOTIFY: link de uma música do Spotify que você tem direito de copiar."""
    url = os.environ.get("BAIXAI_LIVE_SPOTIFY")
    if not url:
        pytest.skip("defina BAIXAI_LIVE_SPOTIFY")
    from baixai_helper.service import Service

    svc = Service()
    a = svc.analyze(url)
    assert a["platform"] == "spotify" and a["modes"] == ["audio"]
    svc.settings.update({"download_dir": str(tmp_path)})
    svc.start()
    try:
        jid = svc.queue.enqueue(url, "audio", {"audio_format": "mp3"}, force=True)["job"]["id"]
        assert svc.queue.wait_idle(600)
        job = next(j for j in svc.queue.list(10) if j["id"] == jid)
        assert job["state"] == "done", job.get("error")
        assert job["files"][0]["path"].endswith(".mp3") and any("YouTube" in n for n in job["notes"])
    finally:
        svc.shutdown()
