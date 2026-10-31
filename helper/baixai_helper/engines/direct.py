"""Adaptador de download direto de mídia (imagem/áudio/vídeo por URL), com HTTP validado."""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .. import platforms
from ..errors import BaixaiError
from ..sanitize import sanitize_filename
from ..urlsafe import safe_open, validate_url
from .base import JobSpec, Result, RunContext
from .gallerydl import AUD, IMG, VID, kind_of

NAME = "direct"


def _filename(resp, url: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.I) or re.search(r'filename="?([^";]+)"?', cd, re.I)
    name = unquote(m.group(1)) if m else unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    name = sanitize_filename(name or "arquivo")
    if not Path(name).suffix:
        ext = mimetypes.guess_extension((resp.headers.get("Content-Type") or "").split(";")[0].strip()) or ""
        name += ext
    return name


def probe(url: str) -> dict:
    """Descobre o tipo de mídia sem baixar o conteúdo (HEAD e, se preciso, GET parcial)."""
    resp = safe_open(url, method="HEAD", timeout=20)
    try:
        if resp.status >= 400 or not resp.headers.get("Content-Type"):
            resp.close()
            resp = safe_open(url, method="GET", headers={"Range": "bytes=0-0"}, timeout=20)
        if resp.status >= 400:
            raise BaixaiError("unavailable", "O servidor recusou ou não encontrou o arquivo.")
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        name = _filename(resp, resp.final_url)
        ext = Path(name).suffix.lower().lstrip(".")
        kind = ctype.split("/")[0] if ctype.split("/")[0] in ("image", "audio", "video") else kind_of(ext)
        if kind not in ("image", "audio", "video"):
            raise BaixaiError("unsupported", "Esse endereço não é uma imagem, áudio ou vídeo direto, e o site não é uma plataforma reconhecida.")
        length = resp.headers.get("Content-Length")
        cr = resp.headers.get("Content-Range")
        size = int(cr.rsplit("/", 1)[-1]) if cr and cr.rsplit("/", 1)[-1].isdigit() else (int(length) if length and length.isdigit() and resp.status == 200 else None)
        return {"name": name, "ext": ext, "kind": kind, "size": size, "final_url": resp.final_url}
    finally:
        resp.close()


def analyze(url: str, detected: platforms.Detected | None, settings: dict) -> dict:
    info = probe(url)
    kind = info["kind"]
    out = {"engine": NAME, "kind": kind if kind != "image" else "image", "title": info["name"], "author": urlsplit(info["final_url"]).hostname,
           "thumbnail": url if kind == "image" else None, "warnings": [], "modes": []}
    if kind == "image":
        out["image"] = {"items": [{"index": 1, "url": url, "name": info["name"], "ext": info["ext"], "kind": "image", "width": None, "height": None}],
                        "total": 1, "formats": ["original", "jpeg", "png"],
                        "note": "O arquivo original é preservado por padrão. Converter para JPEG descarta transparência e aplica compressão com perda."}
        out["modes"] = ["image"]
    elif kind == "audio":
        out["audio"] = {"source_codec": info["ext"], "source_abr": None, "mp3_bitrates": [128, 192, 256, 320], "can_embed_cover": False,
                        "note": "Uma taxa de bits maior não melhora a qualidade da fonte."}
        out["modes"] = ["audio"]
    else:
        out["video"] = {"formats": [{"height": None, "label": f"Original ({info['ext'].upper() or 'vídeo'})", "codec": "", "mp4_compatible": info["ext"] == "mp4", "needs_merge": False, "size": info["size"], "note": None, "compat_note": None}]}
        out["modes"] = ["video"]
    if info["size"]:
        out["size"] = info["size"]
    return out


def download(spec: JobSpec, outdir: Path, ctx: RunContext) -> Result:
    validate_url(spec.url)
    info = probe(spec.url)
    dest = outdir / info["name"]
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    resp = safe_open(info["final_url"], headers=headers, timeout=30)
    try:
        if resp.status >= 400 and resp.status != 416:
            raise BaixaiError("unavailable", "O servidor recusou o download.", retryable=resp.status >= 500)
        if resp.status == 200:
            have = 0  # servidor ignorou o Range: recomeça
        total = None
        cl = resp.headers.get("Content-Length")
        if cl and cl.isdigit():
            total = int(cl) + have
        got = have
        with open(part, "ab" if have else "wb") as fh:
            while chunk := resp.read(1 << 16):
                ctx.check()
                fh.write(chunk)
                got += len(chunk)
                ctx.progress(min(0.99, got / total) if total else None, "downloading", None)
    finally:
        resp.close()
    part.replace(dest)
    return Result(files=[dest])
