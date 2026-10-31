"""Adaptador do gallery-dl (imagens e galerias)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .. import paths, platforms
from ..errors import BaixaiError
from ..friendly import classify
from ..tools import engine_cmd
from .base import JobSpec, Result, RunContext, run_capture, run_streaming

NAME = "gallerydl"
IMG = {"jpg", "jpeg", "png", "gif", "webp", "avif", "bmp", "tif", "tiff", "heic", "jfif"}
VID = {"mp4", "webm", "mov", "m4v", "mkv"}
AUD = {"mp3", "m4a", "ogg", "opus", "wav", "flac", "aac"}
MAX_ITEMS = 500
LISTED_ITEMS = 300
FILENAME_FMT = "{num:>03}_{filename}.{extension}"


def kind_of(ext: str) -> str:
    e = (ext or "").lower().lstrip(".")
    return "image" if e in IMG else "video" if e in VID else "audio" if e in AUD else "file"


def _first(d: dict, *path_options: tuple[str, ...]) -> str | None:
    for path in path_options:
        cur = d
        for key in path:
            cur = cur.get(key) if isinstance(cur, dict) else None
        if isinstance(cur, str) and cur.strip():
            return cur.strip()
    return None


def pick_author(meta: dict) -> str | None:
    return _first(meta, ("author", "nick"), ("author", "name"), ("user", "nick"), ("user", "name"), ("owner", "username"),
                  ("username",), ("uploader",), ("creator",), ("fullname",))


def pick_title(meta: dict, author: str | None) -> str:
    text = _first(meta, ("content",), ("description",), ("title",), ("caption",))
    if text:
        line = text.splitlines()[0].strip()
        return line[:120] + ("…" if len(line) > 120 else "")
    return f"Publicação de {author}" if author else "Galeria"


def parse_dump(data: list, detected: platforms.Detected) -> dict:
    """Converte a saída de `gallery-dl -j` em nossa estrutura de análise."""
    post_meta: dict = {}
    items: list[dict] = []
    for entry in data:
        if not isinstance(entry, list) or not entry:
            continue
        if entry[0] == 2 and len(entry) > 1 and isinstance(entry[1], dict) and not post_meta:
            post_meta = entry[1]
        elif entry[0] == 3 and len(entry) >= 3 and isinstance(entry[1], str) and isinstance(entry[2], dict):
            url, meta = entry[1], entry[2]
            post_meta = post_meta or meta
            ext = str(meta.get("extension") or "").lower() or url.split("?")[0].rsplit(".", 1)[-1].lower()
            items.append({
                "index": len(items) + 1, "url": url, "ext": ext, "kind": kind_of(ext),
                "name": f"{meta.get('filename', 'arquivo')}.{ext}" if ext else str(meta.get("filename", "arquivo")),
                "width": meta.get("width"), "height": meta.get("height"),
            })
    if not items:
        raise BaixaiError("no_media", "Não foi encontrada mídia nesse link para este mecanismo.")
    author = pick_author(post_meta)
    kinds = {i["kind"] for i in items}
    warnings = []
    if "video" in kinds or "audio" in kinds:
        warnings.append("Esta publicação inclui vídeo ou áudio; eles serão baixados no formato original (sem conversão).")
    return {
        "engine": NAME, "kind": "gallery" if len(items) > 1 else "image",
        "title": pick_title(post_meta, author), "author": author,
        "thumbnail": next((i["url"] for i in items if i["kind"] == "image"), None),
        "entry_count": len(items), "truncated": len(items) >= MAX_ITEMS,
        "image": {
            "items": [{k: i[k] for k in ("index", "url", "name", "ext", "kind", "width", "height")} for i in items[:LISTED_ITEMS]],
            "total": len(items), "formats": ["original", "jpeg", "png"],
            "note": "O arquivo original é preservado por padrão. Converter para JPEG descarta transparência e aplica compressão com perda.",
        },
        "modes": ["image"], "warnings": warnings,
    }


def ranges(indices: list[int]) -> str:
    out, idx = [], sorted(set(indices))
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1:
            j += 1
        out.append(str(idx[i]) if i == j else f"{idx[i]}-{idx[j]}")
        i = j + 1
    return ",".join(out)


def config_file() -> Path:
    conf = paths.data_dir() / "gallery-dl.conf"
    conf.write_text(json.dumps({
        "extractor": {"sleep-request": 0.5},
        "downloader": {"retries": 4, "timeout": 30, "part": True},
    }), encoding="utf-8")
    return conf


def _base(settings: dict) -> list[str]:
    found = engine_cmd("gallerydl", settings)
    if not found:
        raise BaixaiError("engine_missing", "O gallery-dl não está instalado. Veja o Diagnóstico.")
    return [*found[0], "--config-ignore", "-c", str(config_file())]


def build_download_args(base: list[str], spec: JobSpec, outdir: Path) -> list[str]:
    args = [*base, "-D", str(outdir), "-f", FILENAME_FMT, "--no-mtime"]
    if spec.options.get("items"):
        args += ["--range", ranges(spec.options["items"])]
    return [*args, "--", spec.url]


def analyze(url: str, detected: platforms.Detected, settings: dict) -> dict:
    args = [*_base(settings), "-j", "--range", f"1-{MAX_ITEMS}", "--", url]
    try:
        rc, out, err = run_capture(args, timeout=120)
    except subprocess.TimeoutExpired:
        raise BaixaiError("timeout", "A análise demorou demais. Tente novamente.", retryable=True) from None
    if rc != 0 and not out.strip():
        raise classify(err, NAME)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        raise classify(err or "no media", NAME) from None
    return parse_dump(data, detected)


def download(spec: JobSpec, outdir: Path, ctx: RunContext) -> Result:
    args = build_download_args(_base(ctx.settings), spec, outdir)
    total = len(spec.options["items"]) if spec.options.get("items") else spec.meta.get("count")
    prefix = str(outdir)
    files: list[str] = []

    def on_line(line: str) -> None:
        raw = line[2:] if line.startswith("# ") else line  # "# caminho" = já existia
        if raw.startswith(prefix):
            files.append(raw)
            ctx.progress(min(0.99, len(files) / total) if total else None, "downloading", f"{len(files)} arquivo(s)")
        else:
            ctx.log(line)

    rc, tail = run_streaming(args, ctx, on_line)
    out = [Path(f) for f in dict.fromkeys(files) if Path(f).is_file()]
    if not out:
        raise classify("\n".join(tail), NAME) if rc != 0 else BaixaiError("no_output", "Nenhum arquivo foi baixado.")
    notes = [f"Concluído parcialmente: {len(out)} de {total} arquivo(s)."] if rc != 0 and total and len(out) < total else []
    return Result(files=out, notes=notes)
