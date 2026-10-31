"""Spotify: reconhecimento de links, leitura dos metadados públicos e escolha da música no YouTube (sem rede)."""
import json
from pathlib import Path

import pytest

from baixai_helper import platforms, terminal
from baixai_helper.engines import spotify as sp
from baixai_helper.engines import ytdlp
from baixai_helper.engines.base import JobSpec, Result
from baixai_helper.errors import BaixaiError

TID = "a" * 22


def embed_html(entity: dict) -> str:
    data = {"props": {"pageProps": {"state": {"data": {"entity": entity}}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


TRACK = {"type": "track", "id": TID, "title": "Cancao Inventada (feat. Outra Pessoa)", "duration": 200_500,
         "artists": [{"name": "Banda Exemplo", "uri": "spotify:artist:x"}, {"name": "Outra Pessoa", "uri": "spotify:artist:y"}]}
ALBUM = {"type": "album", "title": "Disco Exemplo", "subtitle": "Banda Exemplo", "trackList": [
    {"uri": f"spotify:track:{'b' * 22}", "title": "Faixa Um", "subtitle": "Banda Exemplo", "duration": 180_000},
    {"uri": "spotify:episode:zzz", "title": "Episodio de podcast", "subtitle": "Alguem", "duration": 999_000},
    {"uri": f"spotify:track:{'c' * 22}", "title": "Faixa Dois", "subtitle": "Banda Exemplo", "duration": 0},
]}


# ---------------------------------------------------------------- links
@pytest.mark.parametrize("url, kind, typ", [
    (f"https://open.spotify.com/track/{TID}", "track", "track"),
    (f"https://open.spotify.com/track/{TID}?si=xyz", "track", "track"),
    (f"https://open.spotify.com/intl-pt/track/{TID}", "track", "track"),
    (f"https://open.spotify.com/album/{TID}", "playlist", "album"),
    (f"https://open.spotify.com/playlist/{TID}", "playlist", "playlist"),
])
def test_links_suportados(url, kind, typ):
    d = platforms.detect(url)
    assert d.platform == "spotify" and d.supported and d.kind == kind and d.engines == ("spotify",)
    assert d.extra == {"type": typ, "id": TID}


@pytest.mark.parametrize("url, needle", [
    (f"https://open.spotify.com/episode/{TID}", "Podcasts"),
    (f"https://open.spotify.com/show/{TID}", "Podcasts"),
    (f"https://open.spotify.com/artist/{TID}", "música, álbum ou playlist"),
    ("https://open.spotify.com/track/curto", "música, álbum ou playlist"),
])
def test_links_nao_suportados_explicam(url, needle):
    d = platforms.detect(url)
    assert d.platform == "spotify" and not d.supported and needle in d.note


def test_dominio_imitador_nao_e_spotify():
    assert platforms.detect(f"https://open.spotify.com.example.net/track/{TID}") is None
    assert platforms.detect(f"https://notspotify.com/track/{TID}") is None


# ---------------------------------------------------------------- metadados públicos
def test_le_faixa_com_varios_artistas():
    t = sp.track_from_entity(sp.parse_embed(embed_html(TRACK)))
    assert t == {"id": TID, "title": "Cancao Inventada (feat. Outra Pessoa)", "artist": "Banda Exemplo, Outra Pessoa",
                 "artists": ["Banda Exemplo", "Outra Pessoa"], "duration": 200.5}
    assert sp.label(t) == "Banda Exemplo - Cancao Inventada (feat. Outra Pessoa)"  # o convidado já está no título
    assert sp.label({**t, "title": "Outra Cancao"}) == "Banda Exemplo, Outra Pessoa - Outra Cancao"
    assert sp.primary_artist({"artists": ["Tyler, The Creator"], "artist": "Tyler, The Creator"}) == "Tyler, The Creator"


def test_lista_ignora_podcasts_e_duracao_zero_vira_none():
    tracks = sp.tracks_from_list(sp.parse_embed(embed_html(ALBUM)))
    assert [t["id"] for t in tracks] == ["b" * 22, "c" * 22]
    assert tracks[1]["duration"] is None


@pytest.mark.parametrize("html", ["<html>sem dados</html>", '<script id="__NEXT_DATA__">{nao e json</script>',
                                  '<script id="__NEXT_DATA__">{"props": {}}</script>'])
def test_pagina_ilegivel_da_erro_claro(html):
    with pytest.raises(BaixaiError) as e:
        sp.parse_embed(html)
    assert e.value.code == "spotify_unreadable"


def test_analise_de_album_vira_lista_de_faixas(monkeypatch):
    monkeypatch.setattr(sp, "fetch_entity", lambda kind, i: ALBUM)
    a = sp.analyze("u", platforms.detect(f"https://open.spotify.com/album/{TID}"), {})
    assert a["kind"] == "playlist" and a["modes"] == ["audio"] and a["entry_count"] == 2
    assert a["entries"][0] == {"index": 1, "url": f"https://open.spotify.com/track/{'b' * 22}", "title": "Banda Exemplo - Faixa Um", "duration": 180.0}
    assert any("DRM" in w for w in a["warnings"])


def test_analise_de_faixa(monkeypatch):
    monkeypatch.setattr(sp, "fetch_entity", lambda kind, i: TRACK)
    a = sp.analyze("u", platforms.detect(f"https://open.spotify.com/track/{TID}"), {})
    assert a["kind"] == "track" and a["modes"] == ["audio"] and a["title"].startswith("Banda Exemplo - ")


# ---------------------------------------------------------------- escolha no YouTube
T = {"title": "Cancao Inventada (feat. Outra Pessoa)", "artist": "Banda Exemplo, Outra Pessoa", "duration": 200.5}


def cand(i, title, channel, duration):
    return {"id": f"vid{i}", "title": title, "channel": channel, "duration": duration}


def test_prefere_audio_oficial_com_duracao_certa():
    cands = [
        cand(1, "Banda Exemplo - Cancao Inventada (Ao Vivo)", "Banda Exemplo", 260),
        cand(2, "Cancao Inventada - cover acustico", "Fulano Covers", 201),
        cand(3, "Cancao Inventada", "Banda Exemplo - Topic", 200),
        cand(4, "Banda Exemplo - Cancao Inventada (Lyrics)", "Canal de Letras", 201),
    ]
    best, sc = sp.pick_best(T, cands)
    assert best["id"] == "vid3" and sc >= sp.STRONG_SCORE


def test_canal_do_artista_vence_reupload():
    cands = [cand(1, "Banda Exemplo - Cancao Inventada (Lyrics)", "Canal de Letras", 201),
             cand(2, "Banda Exemplo - Cancao Inventada (Official Video)", "Banda Exemplo", 201)]
    assert sp.pick_best(T, cands)[0]["id"] == "vid2"


def test_versao_ao_vivo_e_aceita_quando_o_spotify_tambem_e_ao_vivo():
    live = {**T, "title": "Cancao Inventada - Ao Vivo"}
    best, _ = sp.pick_best(live, [cand(1, "Banda Exemplo - Cancao Inventada (Ao Vivo)", "Banda Exemplo", 200)])
    assert best["id"] == "vid1"


def test_sem_correspondencia_confiavel_nao_baixa_nada():
    with pytest.raises(BaixaiError) as e:
        sp.pick_best(T, [cand(1, "Outra musica qualquer", "Alguem", 95), cand(2, "Cancao Inventada karaoke", "Karaoke BR", 420)])
    assert e.value.code == "no_match" and "Nada foi baixado" in e.value.message
    with pytest.raises(BaixaiError):
        sp.pick_best(T, [])


def test_busca_fica_depois_de_dois_tracos_e_sem_controles(monkeypatch):
    seen = {}

    def runner(args, timeout):
        seen["args"] = args
        return 0, json.dumps({"entries": [cand(1, "Cancao Inventada", "Banda Exemplo - Topic", 200)]}), ""

    monkeypatch.setattr(ytdlp, "_cmd", lambda s: ["yt-dlp"])
    evil = {**T, "artist": "--exec rm\n-rf", "title": "Cancao\x00Inventada"}
    m, _ = sp.find_on_youtube({**T}, {}, runner=runner)
    assert m["url"] == "https://www.youtube.com/watch?v=vid1"
    args = seen["args"]
    assert args[-2] == "--" and args[-1].startswith("ytsearch8:") and "Cancao Inventada" in args[-1]
    assert "\x00" not in sp.search_query(evil) and "\n" not in sp.search_query(evil)


# ---------------------------------------------------------------- download: busca e entrega ao yt-dlp com o nome do Spotify
def test_download_resolve_no_youtube_e_nomeia_pelo_spotify(monkeypatch, tmp_path):
    monkeypatch.setattr(sp, "fetch_entity", lambda kind, i: TRACK)
    monkeypatch.setattr(sp, "find_on_youtube", lambda t, s: ({"url": "https://www.youtube.com/watch?v=vid3", "title": "Cancao Inventada", "channel": "Banda Exemplo - Topic", "duration": 200}, 12))
    got = {}

    def fake_download(spec, outdir, ctx):
        got["spec"] = spec
        return Result(files=[tmp_path / "x.mp3"])

    monkeypatch.setattr(ytdlp, "download", fake_download)

    class Ctx:
        settings: dict = {}
        def progress(self, *a, **k): pass
        def check(self): pass
        def log(self, line): pass

    spec = JobSpec("j1", f"https://open.spotify.com/track/{TID}", "spotify", "spotify", "audio", {"audio_format": "mp3", "mp3_bitrate": 192}, {})
    res = sp.download(spec, tmp_path, Ctx())
    inner = got["spec"]
    assert inner.url == "https://www.youtube.com/watch?v=vid3" and inner.engine == "ytdlp" and inner.mode == "audio"
    assert inner.meta["filename"] == "Banda Exemplo - Cancao Inventada (feat. Outra Pessoa)"
    assert any("Áudio do YouTube" in n for n in res.notes) and not any("incerta" in n for n in res.notes)


def test_nome_do_arquivo_do_ytdlp_e_sanitizado_e_escapado():
    spec = JobSpec("j", "https://www.youtube.com/watch?v=x", "youtube", "ytdlp", "audio", {"audio_format": "mp3"}, {"filename": "A/B: 100% <C>"})
    args = ytdlp.build_download_args(["yt-dlp"], spec, Path("/tmp/x"), {})
    tmpl = args[args.index("-o") + 1]
    assert tmpl.endswith(".%(ext)s") and "/" not in tmpl and "100%%" in tmpl and "<" not in tmpl
    plain = JobSpec("j", "https://www.youtube.com/watch?v=x", "youtube", "ytdlp", "audio", {}, {})
    pargs = ytdlp.build_download_args(["yt-dlp"], plain, Path("/tmp/x"), {})
    assert pargs[pargs.index("-o") + 1] == "%(title).180B.%(ext)s"


def test_terminal_escolhe_audio_para_spotify():
    class Svc:
        def analyze(self, url):
            return {"url": url, "title": "x", "modes": ["audio"], "warnings": [], "defaults": {"default_height": 1080, "default_mp3_bitrate": 192, "default_image_format": "original"}}

    from types import SimpleNamespace

    a = SimpleNamespace(audio=False, imagem=False, qualidade=None, pasta=None, bitrate=None, original=False, formato_imagem=None, tudo=False, itens=None, detalhes=False)
    (_, mode, opts, _), = terminal.plan(Svc(), f"https://open.spotify.com/track/{TID}", a)
    assert mode == "audio" and opts["audio_format"] == "mp3"


def test_fila_aceita_spotify_so_em_audio(tmp_path):
    from baixai_helper.service import Service

    svc = Service()
    with pytest.raises(BaixaiError):
        svc.queue.enqueue(f"https://open.spotify.com/track/{TID}", "video", {})
    job = svc.queue.enqueue(f"https://open.spotify.com/track/{TID}", "audio", {})["job"]
    assert job["engine"] == "spotify" and job["platform"] == "spotify"
    svc.queue.cancel(job["id"])
