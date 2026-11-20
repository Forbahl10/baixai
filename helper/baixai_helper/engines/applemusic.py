"""Apple Music: a extensão lê metadados da página; o áudio vem do YouTube.

Nenhum cookie, token ou fluxo de mídia do Apple Music é recebido pelo host.
"""
from __future__ import annotations

from .. import platforms
from ..errors import BaixaiError
from ..urlsafe import validate_url
from . import spotify, ytdlp
from .base import JobSpec, Result, RunContext

NAME = "applemusic"
SOURCE_NOTE = ("O áudio vem do YouTube, não do Apple Music. Pode haver diferença de versão ou qualidade; "
               "confira a gravação depois do download.")


def analyze(url: str, detected: platforms.Detected, settings: dict, page: dict | None = None) -> dict:
    if not page:
        raise BaixaiError("browser_required", "Abra esta playlist no Apple Music em uma aba do navegador e clique em 'Usar aba atual' na extensão Baixaí.")
    if detected.kind != "playlist":
        raise BaixaiError("unsupported", "Para músicas avulsas do Apple Music, use uma playlist na aba atual.")
    title = page["title"].strip()
    if not title:
        raise BaixaiError("empty", "A página não informou o nome da playlist.")
    entries = []
    for i, track in enumerate(page["tracks"], 1):
        checked = validate_url(track["url"])
        song = platforms.detect(checked.url)
        if not song or song.platform != NAME or song.kind != "track":
            raise BaixaiError("invalid_payload", "Uma faixa da página não possui link de música válido do Apple Music.")
        name, artist = track["title"].strip(), track["artist"].strip()
        if not name or not artist:
            raise BaixaiError("invalid_payload", "Uma faixa da página está sem título ou artista.")
        entries.append({"index": i, "url": checked.url, "title": name, "artist": artist, "duration": track["duration"]})
    if not entries:
        raise BaixaiError("empty", "Não encontrei faixas na página. Aguarde ela carregar e tente novamente.")
    return {"engine": NAME, "kind": "playlist", "title": title, "author": None, "thumbnail": None,
            "modes": ["audio"], "warnings": [SOURCE_NOTE], "audio": spotify._audio_info(),
            "entry_count": len(entries), "entries": entries, "truncated": False}


def download(spec: JobSpec, outdir, ctx: RunContext) -> Result:
    det = platforms.detect(spec.url)
    if not det or det.platform != NAME or det.kind != "track":
        raise BaixaiError("invalid_option", "Este trabalho precisa do link de uma música do Apple Music.")
    meta = spec.meta or {}
    title, artist, duration = meta.get("title"), meta.get("author"), meta.get("duration")
    if not isinstance(title, str) or not title.strip() or not isinstance(artist, str) or not artist.strip() or not isinstance(duration, int) or duration <= 0:
        raise BaixaiError("missing_metadata", "Faltam os metadados da música. Abra a playlist na aba do Apple Music e adicione-a novamente.")
    track = {"title": title, "artist": artist, "duration": duration}
    ctx.progress(None, "downloading", "procurando no YouTube")
    try:
        match, sc = spotify.find_on_youtube(track, ctx.settings)
    except BaixaiError as err:
        if err.code != "no_match":
            raise
        match, sc = spotify.find_on_youtube(track, ctx.settings, query=f"{artist} {title} official")
    ctx.check()
    ctx.log(f"applemusic: {spotify.label(track)} -> {match['url']} (pontos {sc})")
    inner = JobSpec(spec.id, match["url"], "youtube", "ytdlp", "audio", spec.options,
                    {**meta, "filename": spotify.label(track)})
    result = ytdlp.download(inner, outdir, ctx)
    result.notes = [f"Áudio do YouTube: '{match['title']}' ({match['channel']}). Confira se é a versão certa.", *result.notes]
    if sc < spotify.STRONG_SCORE:
        result.notes.append("Correspondência incerta: confira título, artista e duração.")
    result.title, result.author = spotify.label(track), artist
    return result
