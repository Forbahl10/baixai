from __future__ import annotations

import pytest
from types import SimpleNamespace

from baixai_helper import platforms
from baixai_helper.engines import applemusic
from baixai_helper.errors import BaixaiError
from baixai_helper.protocol import validate_request
from baixai_helper.queue import JobQueue
from baixai_helper.engines.base import JobSpec


PLAYLIST = "https://music.apple.com/br/library/playlist/p.7PkeAkzi0pJ5o2B"
SONG = "https://music.apple.com/br/song/discombobulated/123456789"
PAGE = {"title": "SOM DE NOIA", "tracks": [{"url": SONG, "title": "Discombobulated", "artist": "TB-203", "duration": 339}]}


def test_detects_apple_music_playlist_and_song():
    assert platforms.detect(PLAYLIST).kind == "playlist"
    assert platforms.detect("https://music.apple.com/br/playlist/minha-lista/pl.u-abc_123").kind == "playlist"
    assert platforms.detect(SONG).kind == "track"
    assert platforms.detect(PLAYLIST).platform == "applemusic"


def test_playlist_requires_browser_metadata_and_keeps_order(monkeypatch):
    monkeypatch.setattr(applemusic, "validate_url", lambda url: SimpleNamespace(url=url))
    detected = platforms.detect(PLAYLIST)
    with pytest.raises(BaixaiError, match="Usar aba atual"):
        applemusic.analyze(PLAYLIST, detected, {}, None)
    result = applemusic.analyze(PLAYLIST, detected, {}, PAGE)
    assert result["entry_count"] == 1
    assert result["entries"] == [{"index": 1, **PAGE["tracks"][0]}]
    assert result["modes"] == ["audio"]


def test_rejects_external_track_and_unvalidated_page_fields(monkeypatch):
    monkeypatch.setattr(applemusic, "validate_url", lambda url: SimpleNamespace(url=url))
    detected = platforms.detect(PLAYLIST)
    with pytest.raises(BaixaiError):
        applemusic.analyze(PLAYLIST, detected, {}, {"title": "x", "tracks": [{**PAGE["tracks"][0], "url": "https://example.com/song/a/123"}]})
    _, cmd, payload = validate_request({"cmd": "analyze", "payload": {"url": PLAYLIST, "page": PAGE}})
    assert cmd == "analyze" and payload["page"] == PAGE
    with pytest.raises(Exception):
        validate_request({"cmd": "analyze", "payload": {"url": PLAYLIST, "page": {**PAGE, "cookie": "secret"}}})


def test_organizes_tracks_under_playlist_in_order(tmp_path):
    source = tmp_path / "source.mp3"
    source.write_bytes(b"fake mp3")

    class Settings:
        def all(self):
            return {"organize_by_platform": True, "organize_by_author": False}

        def download_dir(self):
            return tmp_path / "downloads"

    queue = JobQueue(store=None, settings=Settings(), tools=None)
    spec = JobSpec("1", SONG, "applemusic", "applemusic", "audio", {},
                   {"playlist": "SOM DE NOIA", "playlist_index": 3, "author": "TB-203"})
    files, destination = queue._finalize(spec, [source])
    assert destination == tmp_path / "downloads" / "Apple Music" / "SOM DE NOIA"
    assert files[0].name == "03 - source.mp3"
    assert files[0].exists()
