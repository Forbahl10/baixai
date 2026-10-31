"""Registro de plataformas: reconhece o link, o tipo de conteúdo e os mecanismos candidatos.

Somente hosts conhecidos vão para yt-dlp/gallery-dl (o extrator genérico do yt-dlp fica
desligado). Links de outros servidores só são aceitos se forem mídia direta (ver engines/direct.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit


@dataclass(frozen=True)
class Detected:
    platform: str  # id: youtube, instagram, tiktok, twitter, soundcloud, direct
    label: str
    kind: str  # video | playlist | channel | post | photo | track | profile | unknown
    engines: tuple[str, ...]  # ordem de tentativa
    supported: bool = True
    note: str | None = None
    extra: dict = field(default_factory=dict)


_HOSTS = {
    "youtube": ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    "instagram": ("instagram.com",),
    "tiktok": ("tiktok.com",),
    "twitter": ("twitter.com", "x.com"),
    "soundcloud": ("soundcloud.com",),
}
LABELS = {"youtube": "YouTube", "instagram": "Instagram", "tiktok": "TikTok", "twitter": "X (Twitter)", "soundcloud": "SoundCloud", "direct": "Link direto"}


def platform_of_host(host: str) -> str | None:
    host = host.lower().rstrip(".")
    for pid, domains in _HOSTS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return pid
    return None


def detect(url: str) -> Detected | None:
    """Retorna None quando o host não é de uma plataforma conhecida."""
    sp = urlsplit(url)
    host = (sp.hostname or "").lower()
    pid = platform_of_host(host)
    if pid is None:
        return None
    path = sp.path or "/"
    q = parse_qs(sp.query)
    label = LABELS[pid]

    if pid == "youtube":
        if host.endswith("youtu.be") and len(path) > 1:
            return Detected(pid, label, "video", ("ytdlp",))
        if path.startswith(("/watch", "/shorts/", "/live/", "/embed/")) or "v" in q and path.startswith("/watch"):
            note = "O link também pertence a uma playlist; só este vídeo será analisado." if "list" in q else None
            return Detected(pid, label, "video", ("ytdlp",), note=note)
        if path.startswith("/playlist") and "list" in q:
            return Detected(pid, label, "playlist", ("ytdlp",))
        if re.match(r"^/(@|channel/|c/|user/)", path):
            return Detected(pid, label, "channel", ("ytdlp",), note="Páginas de canal podem ter milhares de vídeos.")
        return Detected(pid, label, "unknown", (), supported=False, note="Esse tipo de link do YouTube não é reconhecido. Use o link de um vídeo ou playlist.")

    if pid == "instagram":
        if re.match(r"^/(reel|reels|tv)/", path):
            return Detected(pid, label, "video", ("ytdlp", "gallerydl"))
        if re.match(r"^/([^/]+/)?p/", path):
            return Detected(pid, label, "post", ("gallerydl", "ytdlp"))
        if path.startswith("/stories/"):
            return Detected(pid, label, "unknown", (), supported=False, note="Stories exigem login, que não é suportado no MVP.")
        return Detected(pid, label, "unknown", (), supported=False, note="Use o link de uma publicação (/p/...) ou de um reel (/reel/...).")

    if pid == "tiktok":
        if "/photo/" in path:
            return Detected(pid, label, "photo", ("gallerydl", "ytdlp"))
        if "/video/" in path or host.split(".")[0] in ("vm", "vt") or path.startswith("/t/"):
            return Detected(pid, label, "video", ("ytdlp", "gallerydl"))
        return Detected(pid, label, "unknown", (), supported=False, note="Use o link de um vídeo (/@usuario/video/...) ou foto do TikTok.")

    if pid == "twitter":
        if re.match(r"^/[^/]+/status(es)?/\d+", path) or re.match(r"^/i/web/status/\d+", path):
            return Detected(pid, label, "post", ("ytdlp", "gallerydl"))
        return Detected(pid, label, "unknown", (), supported=False, note="Use o link de um post (…/status/…).")

    if pid == "soundcloud":
        parts = [p for p in path.split("/") if p]
        if host.startswith("on."):
            return Detected(pid, label, "track", ("ytdlp",))
        if len(parts) >= 3 and parts[1] == "sets":
            return Detected(pid, label, "playlist", ("ytdlp",))
        if len(parts) == 2 and parts[1] not in ("tracks", "likes", "reposts", "albums", "sets", "popular-tracks"):
            return Detected(pid, label, "track", ("ytdlp",))
        return Detected(pid, label, "unknown", (), supported=False, note="Use o link de uma faixa ou de um set do SoundCloud.")

    return None


def is_compatible_link(url: str) -> bool:
    """Usado pelo menu de contexto (a mesma regra existe na extensão)."""
    d = detect(url)
    return bool(d and d.supported)
