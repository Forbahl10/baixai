"""Construção segura de argumentos e interpretação das saídas dos mecanismos (com fixtures)."""
from pathlib import Path

import pytest

from baixai_helper import platforms
from baixai_helper.engines import gallerydl, ytdlp
from baixai_helper.engines.base import JobSpec

BASE = ["yt-dlp"]
DET = platforms.detect("https://www.youtube.com/watch?v=abc")


def spec(mode, url="https://www.youtube.com/watch?v=abc", **opts):
    return JobSpec("j1", url, "youtube", "ytdlp", mode, opts)


def test_ytdlp_url_sempre_depois_de_dois_hifens_e_ultima(tmp_path):
    args = ytdlp.build_download_args(BASE, spec("video", height=720), tmp_path, {})
    assert args[-2:] == ["--", "https://www.youtube.com/watch?v=abc"]
    assert args.count("--") == 1


def test_ytdlp_url_maliciosa_vira_um_unico_argumento(tmp_path):
    evil = "https://www.youtube.com/watch?v=a;rm -rf ~ && $(id) `id` --exec touch /tmp/x"
    args = ytdlp.build_download_args(BASE, spec("video", url=evil), tmp_path, {})
    assert args[-1] == evil and args.count(evil) == 1 and isinstance(args, list)


def test_ytdlp_flags_de_seguranca(tmp_path):
    args = ytdlp.build_download_args(BASE, spec("video"), tmp_path, {})
    for flag in ("--ignore-config", "--no-plugin-dirs", "--no-exec", "--no-playlist", "--windows-filenames", "--no-overwrites"):
        assert flag in args
    assert args[args.index("--use-extractors") + 1] == "default,-generic"
    assert "--cookies" not in args and "--cookies-from-browser" not in args


def test_ytdlp_video_mp4_com_altura():
    sel = ytdlp.video_selector(720, "mp4")
    assert "height<=720" in sel and "avc1" in sel and sel.count("/") >= 3
    assert "height" not in ytdlp.video_selector(None, "original")


def test_ytdlp_mp4_pede_remux_e_merge(tmp_path):
    a = ytdlp.build_download_args(BASE, spec("video", height=480, container="mp4"), tmp_path, {})
    assert a[a.index("--merge-output-format") + 1] == "mp4" and "--remux-video" in a
    b = ytdlp.build_download_args(BASE, spec("video", container="original"), tmp_path, {})
    assert "--merge-output-format" not in b


def test_ytdlp_audio_mp3_bitrate_e_original(tmp_path):
    a = ytdlp.build_download_args(BASE, spec("audio", audio_format="mp3", mp3_bitrate=256), tmp_path, {})
    assert a[a.index("--audio-format") + 1] == "mp3" and a[a.index("--audio-quality") + 1] == "256K"
    assert "--embed-thumbnail" in a and "--embed-metadata" in a
    b = ytdlp.build_download_args(BASE, spec("audio", audio_format="original"), tmp_path, {})
    assert b[b.index("--audio-format") + 1] == "best" and "--audio-quality" not in b


def test_gallerydl_args(tmp_path):
    s = JobSpec("j", "https://x.com/u/status/1", "twitter", "gallerydl", "image", {"items": [1, 2, 3, 7]})
    a = gallerydl.build_download_args(["gallery-dl", "--config-ignore", "-c", "c.conf"], s, tmp_path)
    assert a[a.index("--range") + 1] == "1-3,7" and a[-2:] == ["--", s.url] and "-D" in a
    assert gallerydl.ranges([5, 1, 2, 3, 9, 10]) == "1-3,5,9-10"


# ---------- fixtures sintéticas, modeladas nas saídas reais capturadas em 2026-10-30
def fmt(fid, ext, h=None, vcodec="none", acodec="none", tbr=100, size=None, note=None, abr=None, w=None, fps=30):
    return {"format_id": fid, "ext": ext, "height": h, "width": w, "vcodec": vcodec, "acodec": acodec, "tbr": tbr, "filesize": size,
            "format_note": note, "abr": abr, "fps": fps, "protocol": "https"}


YT = {
    "_type": "video", "id": "abc", "title": "Vídeo de teste", "uploader": "Canal", "duration": 217, "thumbnail": "https://i.ytimg.com/x.jpg",
    "live_status": "not_live", "age_limit": 0,
    "formats": [
        fmt("sb0", "mhtml", 45, "none", "none"),
        fmt("140", "m4a", acodec="mp4a.40.2", abr=129, size=3_500_000),
        fmt("251", "webm", acodec="opus", abr=136, size=3_700_000),
        fmt("137", "mp4", 1080, "avc1.640028", w=1920, size=100_000_000, note="1080p", tbr=3800),
        fmt("248", "webm", 1080, "vp09.00", w=1920, size=60_000_000, note="1080p", tbr=2200),
        fmt("247", "webm", 720, "vp09.00", w=1280, size=20_000_000, note="720p"),   # 720p só em VP9
        fmt("399", "mp4", 1080, "av01.0", w=1920, size=30_000_000, note="1080p", tbr=1200),
        fmt("616", "mp4", 1080, "avc1.64", note="Premium", tbr=9000),
        fmt("18", "mp4", 360, "avc1.42", "mp4a.40.2", w=640, size=9_000_000, note="360p"),  # já combinado
    ],
}


def test_parse_video_resolucoes_reais_e_codec():
    r = ytdlp.parse_single(YT, DET)
    by_h = {f["height"]: f for f in r["video"]["formats"]}
    assert list(by_h) == [1080, 720, 360]  # ordenado, sem inventar resoluções
    assert by_h[1080]["codec"] == "H.264" and by_h[1080]["mp4_compatible"] and by_h[1080]["needs_merge"]
    assert by_h[1080]["size"] == 100_000_000 + 3_700_000 or by_h[1080]["size"] == 100_000_000 + 3_500_000 or by_h[1080]["size"] > 100_000_000
    assert by_h[720]["codec"] == "VP9" and not by_h[720]["mp4_compatible"] and by_h[720]["compat_note"]
    assert not by_h[360]["needs_merge"]  # fonte já traz áudio
    assert r["modes"] == ["video", "audio"] and r["title"] == "Vídeo de teste" and r["author"] == "Canal"


def test_parse_exclui_premium_e_storyboard():
    r = ytdlp.parse_single(YT, DET)
    assert all(f["height"] != 45 for f in r["video"]["formats"])
    assert [f["size"] for f in r["video"]["formats"] if f["height"] == 1080][0] < 9_000_000_000


def test_parse_audio_informa_fonte_sem_prometer_qualidade():
    a = ytdlp.parse_single(YT, DET)["audio"]
    assert a["source_abr"] == 136 and a["mp3_bitrates"] == [128, 192, 256, 320] and "não melhora" in a["note"]


def test_parse_so_audio_soundcloud():
    info = {"title": "Faixa", "uploader": "Art", "formats": [fmt("http_mp3", "mp3", acodec="mp3", abr=128)], "thumbnail": "https://i1.sndcdn.com/x.jpg"}
    r = ytdlp.parse_single(info, platforms.detect("https://soundcloud.com/a/b"))
    assert r["modes"] == ["audio"] and "video" not in r and r["kind"] == "audio"


def test_parse_ao_vivo_nao_oferece_downloads():
    r = ytdlp.parse_single({**YT, "live_status": "is_live"}, DET)
    assert r["modes"] == [] and r["warnings"]


def test_parse_playlist():
    info = {"_type": "playlist", "title": "Lista", "uploader": "Canal", "entries": [{"id": "a", "url": "https://www.youtube.com/watch?v=a", "title": "A"}, {"id": "b", "title": "B"}, None]}
    r = ytdlp.parse_playlist(info, platforms.detect("https://www.youtube.com/playlist?list=PL1"))
    assert r["kind"] == "playlist" and r["entry_count"] == 2 and r["entries"][1]["url"].endswith("v=b")


GDL = [
    [2, {"category": "twitter", "author": {"nick": "Fulano", "name": "fulano"}, "content": "Texto do post\nsegunda linha", "tweet_id": 1}],
    [3, "https://pbs.twimg.com/media/AAA?format=jpg&name=orig", {"filename": "AAA", "extension": "jpg", "num": 1, "width": 600, "height": 400, "author": {"nick": "Fulano"}, "content": "Texto do post"}],
    [3, "https://pbs.twimg.com/media/BBB?format=png&name=orig", {"filename": "BBB", "extension": "png", "num": 2, "width": 10, "height": 10}],
]


def test_parse_gallerydl():
    r = gallerydl.parse_dump(GDL, platforms.detect("https://x.com/u/status/1"))
    assert r["engine"] == "gallerydl" and r["kind"] == "gallery" and r["entry_count"] == 2 and r["author"] == "Fulano"
    assert r["title"] == "Texto do post" and [i["index"] for i in r["image"]["items"]] == [1, 2] and r["modes"] == ["image"]
    assert r["image"]["formats"] == ["original", "jpeg", "png"] and "transparência" in r["image"]["note"]


def test_parse_gallerydl_vazio_e_erro():
    from baixai_helper.errors import BaixaiError
    with pytest.raises(BaixaiError) as e:
        gallerydl.parse_dump([[2, {}]], platforms.detect("https://x.com/u/status/1"))
    assert e.value.code == "no_media"


def test_erros_amigaveis_sem_vazar_segredos():
    from baixai_helper.friendly import classify
    e = classify("ERROR: [instagram] ABC: login required. Cookie: sessionid=SEGREDO https://x.com/a?token=SEGREDO")
    assert e.code == "auth_required" and "SEGREDO" not in (e.detail or "")
    assert classify("ERROR: ffmpeg not found").code == "ffmpeg_missing"
    assert classify("HTTP Error 429: Too Many Requests").retryable
    assert classify("algo totalmente inesperado").code == "engine_error"
