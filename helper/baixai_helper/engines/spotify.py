"""Spotify: lê só os metadados públicos (título, artista, duração) e baixa a mesma música do YouTube.

O áudio do Spotify é protegido por DRM e NUNCA é baixado nem decifrado aqui. Para cada faixa, o Baixaí lê a página
pública de incorporação (open.spotify.com/embed/...), procura a música no YouTube com o yt-dlp e escolhe o melhor
resultado por título, artista e duração. Se nenhum resultado for confiável, falha em vez de baixar a música errada.
"""
from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from pathlib import Path

from .. import platforms
from ..errors import BaixaiError
from ..friendly import classify
from ..urlsafe import safe_open
from . import ytdlp
from .base import JobSpec, Result, RunContext, run_capture

NAME = "spotify"
EMBED_URL = "https://open.spotify.com/embed/{type}/{id}"
MAX_PAGE_BYTES = 3_000_000
MAX_TRACKS = 500
SEARCH_RESULTS = 8
MIN_SCORE = 5      # abaixo disso não baixa nada
STRONG_SCORE = 9   # abaixo disso baixa, mas avisa que a correspondência é incerta
DRM_NOTE = ("O Spotify protege o áudio com DRM, então o Baixaí não baixa do Spotify: ele procura a mesma música no YouTube "
            "e baixa o áudio de lá. Pode vir outra versão (ao vivo, clipe, remasterizada); confira o resultado.")
_BAD_WORDS = ("live", "ao vivo", "en vivo", "cover", "remix", "karaoke", "instrumental", "sped up", "slowed", "reverb",
              "nightcore", "8d", "acapella", "a cappella", "reaction", "tutorial", "mashup")


# ------------------------------------------------------------------ metadados públicos (funções puras)
def parse_embed(html: str) -> dict:
    """Extrai a entidade (faixa, álbum ou playlist) do JSON embutido na página pública de incorporação."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    try:
        entity = json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"] if m else None
    except (ValueError, KeyError, TypeError):
        entity = None
    if not isinstance(entity, dict):
        raise BaixaiError("spotify_unreadable", "Não consegui ler as informações públicas deste link do Spotify (a página pode ter mudado ou o conteúdo não é público).")
    return entity


def _artist_names(e: dict) -> list[str]:
    names = [str(a["name"]).strip() for a in (e.get("artists") or []) if isinstance(a, dict) and a.get("name")]
    return names or ([str(e["subtitle"]).strip()] if e.get("subtitle") else [])


def track_from_entity(e: dict) -> dict:
    title = str(e.get("title") or e.get("name") or "").strip()
    if not title:
        raise BaixaiError("spotify_unreadable", "O Spotify não informou o nome desta música.")
    dur = e.get("duration")
    names = _artist_names(e)
    return {"id": e.get("id"), "title": title, "artist": ", ".join(names), "artists": names,
            "duration": (dur / 1000) if isinstance(dur, (int, float)) and dur > 0 else None}


def tracks_from_list(e: dict) -> list[dict]:
    out = []
    for t in e.get("trackList") or []:
        uri = str(t.get("uri") or "")
        if not uri.startswith("spotify:track:") or not t.get("title"):
            continue  # episódios de podcast e itens sem nome ficam de fora
        dur = t.get("duration")
        out.append({"id": uri.rsplit(":", 1)[-1], "title": str(t["title"]).strip(), "artist": str(t.get("subtitle") or "").strip(),
                    "duration": (dur / 1000) if isinstance(dur, (int, float)) and dur > 0 else None})
    return out


def primary_artist(track: dict) -> str:
    """Primeiro artista exato quando a lista existe ('Tyler, The Creator' não é cortado na vírgula)."""
    names = track.get("artists") or []
    return names[0] if names else str(track.get("artist") or "").split(",")[0].strip()


def label(track: dict) -> str:
    """'Artista - Música'; convidados que já aparecem no título (feat.) não se repetem."""
    names = track.get("artists") or []
    if names:
        title_n = _norm(track["title"])
        shown = [names[0], *[a for a in names[1:] if not _has_phrase(title_n, a)]]
        artist = ", ".join(shown)
    else:
        artist = str(track.get("artist") or "")
    return f"{artist} - {track['title']}" if artist else track["title"]


def fetch_entity(kind: str, item_id: str) -> dict:
    resp = safe_open(EMBED_URL.format(type=kind, id=item_id), timeout=30)
    try:
        if resp.status == 429:
            raise BaixaiError("rate_limited", "O Spotify limitou as consultas por agora. Tente de novo em alguns minutos.", retryable=True)
        if resp.status != 200:
            raise BaixaiError("unavailable", f"O Spotify não mostrou este conteúdo (HTTP {resp.status}): pode ser privado, removido ou indisponível na sua região.")
        body, total = [], 0
        while total < MAX_PAGE_BYTES:
            chunk = resp.read(65536)
            if not chunk:
                break
            body.append(chunk)
            total += len(chunk)
    finally:
        resp.close()
    return parse_embed(b"".join(body).decode("utf-8", "replace"))


# ------------------------------------------------------------------ correspondência no YouTube (funções puras)
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _core_title(title: str) -> str:
    """'Nome (feat. X) - Remastered 2011' -> 'Nome'."""
    return re.sub(r"\s*[\(\[].*?[\)\]]", "", title).split(" - ")[0].strip() or title


def _has_phrase(text_norm: str, phrase: str) -> bool:
    return f" {_norm(phrase)} " in f" {text_norm} "


def score(track: dict, cand: dict) -> int:
    title_n = _norm(cand.get("title") or "")
    channel = str(cand.get("channel") or cand.get("uploader") or "")
    want_title = _norm(_core_title(track["title"]))
    full_title_n = _norm(track["title"])
    want_artist = _norm(primary_artist(track))
    s = 0
    if want_title and set(want_title.split()) <= set(title_n.split()):
        s += 3
    if want_artist and _has_phrase(_norm(channel), want_artist):  # canal do próprio artista vale mais que um reupload
        s += 3
    elif want_artist and _has_phrase(title_n, want_artist):
        s += 1
    if channel.endswith(" - Topic"):  # áudio oficial gerado pelo YouTube Music
        s += 3
    d, want_d = cand.get("duration"), track.get("duration")
    if isinstance(d, (int, float)) and want_d:
        diff = abs(d - want_d)
        s += 4 if diff <= 3 else 2 if diff <= 10 else 0 if diff <= 30 else -6
    for bad in _BAD_WORDS:
        if _has_phrase(title_n, bad) and not _has_phrase(full_title_n, bad):
            s -= 4
    return s


def pick_best(track: dict, candidates: list[dict]) -> tuple[dict, int]:
    ranked = sorted(((score(track, c), i, c) for i, c in enumerate(candidates) if c.get("id") or c.get("url")), key=lambda x: (-x[0], x[1]))
    if not ranked or ranked[0][0] < MIN_SCORE:
        raise BaixaiError("no_match", f"Não encontrei \"{label(track)}\" no YouTube com segurança (título, artista e duração não bateram). Nada foi baixado.")
    return ranked[0][2], ranked[0][0]


def search_query(track: dict) -> str:
    q = f"{primary_artist(track)} {_core_title(track['title'])}".strip()
    return re.sub(r"[\x00-\x1f\x7f]", " ", q)[:200]


def find_on_youtube(track: dict, settings: dict, runner=run_capture) -> tuple[dict, int]:
    args = [*ytdlp._cmd(settings), *ytdlp.common_args(settings, playlist=True), "-J", "--flat-playlist",
            "--", f"ytsearch{SEARCH_RESULTS}:{search_query(track)}"]  # depois de "--": o texto vindo do Spotify nunca vira opção
    try:
        rc, out, err = runner(args, timeout=120)
    except subprocess.TimeoutExpired:
        raise BaixaiError("timeout", "A busca no YouTube demorou demais. Tente novamente.", retryable=True) from None
    if rc != 0 or not out.strip():
        raise classify(err, "ytdlp")
    try:
        entries = [e for e in (json.loads(out).get("entries") or []) if isinstance(e, dict)]
    except (json.JSONDecodeError, AttributeError):
        raise BaixaiError("engine_error", "Resposta inesperada do yt-dlp na busca.") from None
    best, sc = pick_best(track, entries)
    vid = best.get("id")
    url = f"https://www.youtube.com/watch?v={vid}" if vid else best["url"]
    return {"url": url, "title": best.get("title") or "", "channel": best.get("channel") or best.get("uploader") or "", "duration": best.get("duration")}, sc


# ------------------------------------------------------------------ interface do adaptador
def _audio_info() -> dict:
    return {"source_codec": None, "source_abr": None, "mp3_bitrates": ytdlp.MP3_BITRATES, "can_embed_cover": True,
            "note": "O áudio vem do YouTube (geralmente 128 a 160 kbps). Uma taxa de bits maior no MP3 não melhora a qualidade."}


def analyze(url: str, detected: platforms.Detected, settings: dict) -> dict:
    kind, item_id = detected.extra["type"], detected.extra["id"]
    e = fetch_entity(kind, item_id)
    base = {"engine": NAME, "thumbnail": None, "modes": ["audio"], "warnings": [DRM_NOTE], "audio": _audio_info()}
    if kind == "track":
        t = track_from_entity(e)
        return {**base, "kind": "track", "title": label(t), "author": t["artist"], "duration": t["duration"]}
    tracks = tracks_from_list(e)
    if not tracks:
        raise BaixaiError("empty", "A página pública desta lista do Spotify não mostrou nenhuma música.")
    if len(tracks) >= 100:
        base["warnings"].append(f"A página pública do Spotify mostrou {len(tracks)} músicas; listas maiores podem vir incompletas.")
    tracks = tracks[:MAX_TRACKS]
    entries = [{"index": i, "url": f"https://open.spotify.com/track/{t['id']}", "title": label(t), "duration": t["duration"]} for i, t in enumerate(tracks, 1)]
    return {**base, "kind": "playlist", "title": e.get("title") or e.get("name"), "author": e.get("subtitle"),
            "entry_count": len(entries), "entries": entries, "truncated": False}


def download(spec: JobSpec, outdir: Path, ctx: RunContext) -> Result:
    det = platforms.detect(spec.url)
    if det is None or det.platform != NAME or det.kind != "track":
        raise BaixaiError("invalid_option", "Para baixar, use o link de uma música do Spotify (álbuns e playlists viram uma tarefa por música).")
    ctx.progress(None, "downloading", "lendo o Spotify")
    track = track_from_entity(fetch_entity("track", det.extra["id"]))
    ctx.check()
    ctx.progress(None, "downloading", "procurando no YouTube")
    match, sc = find_on_youtube(track, ctx.settings)
    ctx.check()
    ctx.log(f"spotify: {label(track)} -> {match['url']} (pontos {sc})")
    inner = JobSpec(spec.id, match["url"], "youtube", "ytdlp", "audio", spec.options, {**spec.meta, "filename": label(track)})
    res = ytdlp.download(inner, outdir, ctx)
    res.notes = [f"Áudio do YouTube: \"{match['title']}\" ({match['channel']}). Confira se é a versão certa.", *res.notes]
    if sc < STRONG_SCORE:
        res.notes.append("Correspondência incerta: o título, o artista ou a duração não bateram totalmente.")
    res.title, res.author = label(track), track["artist"]
    return res
