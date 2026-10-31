"""Adaptador do yt-dlp (vídeo e áudio). Todos os argumentos são montados como lista."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .. import paths, platforms
from ..errors import BaixaiError
from ..friendly import classify
from ..tools import engine_cmd, ffmpeg_path, js_runtime
from .base import JobSpec, Result, RunContext, run_capture, run_streaming

NAME = "ytdlp"
MP3_BITRATES = [128, 192, 256, 320]
MAX_PLAYLIST = 500


# ------------------------------------------------------------------ argumentos
def common_args(settings: dict, *, playlist: bool = False) -> list[str]:
    args = [
        "--ignore-config", "--no-plugin-dirs", "--no-exec", "--color", "never",
        "--use-extractors", "default,-generic",  # nunca o extrator genérico (qualquer site)
        "--socket-timeout", "30", "--retries", "5", "--fragment-retries", "5",
        "--no-mtime", "--windows-filenames",
        "--cache-dir", str(paths.subdir("cache")),
        "--yes-playlist" if playlist else "--no-playlist",
    ]
    ff = ffmpeg_path(settings)
    if ff:
        args += ["--ffmpeg-location", ff]
    rt = js_runtime()
    if rt["ok"]:
        args += ["--js-runtimes", f"{rt['name']}:{rt['path']}"]
    return args


def video_selector(height: int | None, container: str) -> str:
    h = f"[height<={height}]" if height else ""
    if container == "mp4":
        return (
            f"bv*{h}[vcodec~='^(avc1|h264)']+ba[acodec~='^(mp4a|aac)']"
            f"/bv*{h}[vcodec~='^(avc1|h264)']+ba"
            f"/b{h}[ext=mp4]"
            f"/bv*{h}+ba/b{h}"
        )
    return f"bv*{h}+ba/b{h}"


def build_download_args(base: list[str], spec: JobSpec, outdir: Path, settings: dict) -> list[str]:
    o = spec.options
    args = [*base, *common_args(settings), "--newline", "--progress", "--progress-delta", "0.5",
            "--progress-template", "download:BAIXAI_P %(progress.status)s %(progress.downloaded_bytes)s %(progress.total_bytes)s %(progress.total_bytes_estimate)s %(progress.speed)s %(progress.eta)s",
            "--progress-template", "postprocess:BAIXAI_PP %(progress.postprocessor)s %(progress.status)s",
            "--print", "after_move:BAIXAI_FILE %(filepath)s",
            "-P", str(outdir), "-o", "%(title).180B.%(ext)s", "--no-overwrites"]
    if spec.mode == "audio":
        fmt = o.get("audio_format", "mp3")
        args += ["-f", "ba/b", "-x", "--audio-format", "mp3" if fmt == "mp3" else "best", "--embed-metadata", "--embed-thumbnail", "--convert-thumbnails", "jpg"]
        if fmt == "mp3":
            args += ["--audio-quality", f"{int(o.get('mp3_bitrate', 192))}K"]
    else:
        container = o.get("container", "mp4")
        args += ["-f", video_selector(o.get("height"), container), "--embed-metadata"]
        if container == "mp4":
            args += ["--merge-output-format", "mp4", "--remux-video", "mp4"]
    args += ["--", spec.url]
    return args


# ------------------------------------------------------------------ análise (funções puras)
def _is_video(f: dict) -> bool:
    return f.get("vcodec") != "none" and bool(f.get("height")) and f.get("ext") != "mhtml" and "Premium" not in (f.get("format_note") or "")


def _is_audio(f: dict) -> bool:
    return f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")


def _size(f: dict) -> int | None:
    return f.get("filesize") or f.get("filesize_approx")


def _codec_label(vcodec: str | None) -> str:
    v = (vcodec or "").lower()
    if v.startswith(("avc1", "h264")):
        return "H.264"
    if v.startswith(("vp9", "vp09")):
        return "VP9"
    if v.startswith("av01"):
        return "AV1"
    if v.startswith(("hev1", "hvc1", "h265")):
        return "H.265"
    return v.split(".")[0].upper() or "?"


def parse_single(info: dict, detected: platforms.Detected) -> dict:
    fmts = info.get("formats") or ([info] if info.get("url") else [])
    vfmts = [f for f in fmts if _is_video(f)]
    afmts = [f for f in fmts if _is_audio(f)]
    best_audio = max(afmts, key=lambda f: f.get("abr") or 0, default=None)
    author = info.get("uploader") or info.get("channel") or info.get("creator") or info.get("uploader_id")
    warnings: list[str] = []
    if info.get("live_status") in ("is_live", "is_upcoming"):
        warnings.append("Transmissões ao vivo não são suportadas.")
        vfmts, afmts = [], []
    out: dict = {
        "engine": NAME, "kind": "video" if vfmts else "audio",
        "title": info.get("title"), "author": author, "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"), "warnings": warnings, "modes": [],
    }
    if info.get("age_limit", 0) and info["age_limit"] >= 18:
        warnings.append("Conteúdo com restrição de idade: pode exigir login, que não é suportado.")

    video_opts = []
    by_h: dict[int, list[dict]] = {}
    for f in vfmts:
        by_h.setdefault(int(f["height"]), []).append(f)
    for h in sorted(by_h, reverse=True):
        cands = by_h[h]
        h264 = [f for f in cands if (f.get("vcodec") or "").lower().startswith(("avc1", "h264"))]
        pick = max(h264 or cands, key=lambda f: f.get("tbr") or 0)
        muxed = pick.get("acodec") not in (None, "none")
        needs_merge = (not muxed) and best_audio is not None
        size = _size(pick)
        if size and needs_merge and best_audio and _size(best_audio):
            size += _size(best_audio)
        fps = pick.get("fps")
        m = re.match(r"\d{3,4}p", pick.get("format_note") or "")  # rótulo oficial (ex.: 1080p em vídeo 1920×788)
        label = (m.group(0) if m else f"{h}p") + (f" {int(fps)} fps" if fps and fps > 30 else "")
        if pick.get("width"):
            label_detail = f"{pick['width']}×{h}"
        else:
            label_detail = None
        video_opts.append({
            "height": h, "label": label, "detail": label_detail, "codec": _codec_label(pick.get("vcodec")),
            "mp4_compatible": bool(h264) or pick.get("ext") == "mp4", "needs_merge": needs_merge,
            "size": size, "fps": fps,
            "note": ("Vídeo e áudio são baixados separados e combinados com o FFmpeg." if needs_merge else None),
            "compat_note": (None if h264 or pick.get("ext") == "mp4" else f"Esta resolução só existe em {_codec_label(pick.get('vcodec'))}; o MP4 pode não abrir em players antigos."),
        })
    if video_opts:
        out["video"] = {"formats": video_opts}
        out["modes"].append("video")

    if afmts or vfmts:
        src = best_audio or (max(vfmts, key=lambda f: f.get("abr") or 0) if vfmts else None)
        abr = int(src.get("abr")) if src and src.get("abr") else None
        out["audio"] = {
            "source_codec": (src.get("acodec") or "").split(".")[0] if src else None, "source_abr": abr,
            "mp3_bitrates": MP3_BITRATES, "can_embed_cover": True,
            "note": "Uma taxa de bits maior não melhora a qualidade da fonte: o MP3 apenas ocupa mais espaço." + (f" A fonte tem cerca de {abr} kbps." if abr else ""),
        }
        out["modes"].append("audio")
    if not out["modes"] and not warnings:
        warnings.append("Nenhum formato de vídeo ou áudio foi encontrado para este link.")
    return out


def parse_playlist(info: dict, detected: platforms.Detected) -> dict:
    entries = [e for e in (info.get("entries") or []) if e]
    items = []
    for i, e in enumerate(entries[:MAX_PLAYLIST], 1):
        url = e.get("url") or e.get("webpage_url")
        if not url or not str(url).startswith("http"):
            if e.get("id") and detected.platform == "youtube":
                url = f"https://www.youtube.com/watch?v={e['id']}"
            else:
                continue
        items.append({"index": i, "url": url, "title": e.get("title"), "duration": e.get("duration")})
    return {
        "engine": NAME, "kind": "playlist", "title": info.get("title"),
        "author": info.get("uploader") or info.get("channel"), "thumbnail": None,
        "entry_count": len(items), "entry_total_known": info.get("playlist_count"),
        "truncated": len(entries) > MAX_PLAYLIST, "entries": [{**it} for it in items[:300]],
        "modes": ["video", "audio"], "warnings": [],
        "video": {"formats": [{"height": h, "label": f"até {h}p", "codec": "", "mp4_compatible": True, "needs_merge": h > 360, "size": None, "note": None, "compat_note": None} for h in (2160, 1440, 1080, 720, 480, 360)]},
        "audio": {"source_codec": None, "source_abr": None, "mp3_bitrates": MP3_BITRATES, "can_embed_cover": True,
                  "note": "Uma taxa de bits maior não melhora a qualidade da fonte: o MP3 apenas ocupa mais espaço."},
    }


# ------------------------------------------------------------------ operações
def _cmd(settings: dict) -> list[str]:
    found = engine_cmd("ytdlp", settings)
    if not found:
        raise BaixaiError("engine_missing", "O yt-dlp não está instalado. Veja o Diagnóstico.")
    return found[0]


def analyze(url: str, detected: platforms.Detected, settings: dict) -> dict:
    playlist = detected.kind in ("playlist", "channel")
    args = [*_cmd(settings), *common_args(settings, playlist=playlist), "-J"]
    if playlist:
        args += ["--flat-playlist", "--playlist-end", str(MAX_PLAYLIST)]
    args += ["--", url]
    try:
        rc, out, err = run_capture(args, timeout=120)
    except subprocess.TimeoutExpired:
        raise BaixaiError("timeout", "A análise demorou demais. Tente novamente.", retryable=True) from None
    if rc != 0 or not out.strip():
        raise classify(err, NAME)
    try:
        info = json.loads(out)
    except json.JSONDecodeError:
        raise BaixaiError("engine_error", "Resposta inesperada do yt-dlp.") from None
    if info.get("_type") == "playlist" or "entries" in info:
        return parse_playlist(info, detected)
    return parse_single(info, detected)


_P = re.compile(r"^BAIXAI_P (\S+) (\S+) (\S+) (\S+) (\S+) (\S+)")


def _num(s: str) -> float | None:
    try:
        return float(s)
    except ValueError:
        return None


def download(spec: JobSpec, outdir: Path, ctx: RunContext) -> Result:
    args = build_download_args(_cmd(ctx.settings), spec, outdir, ctx.settings)
    streams_expected = 2 if spec.mode == "video" else 1
    state = {"stream": 0}
    files: list[str] = []

    def on_line(line: str) -> None:
        m = _P.match(line)
        if m:
            status, done, total, est, speed, eta = m.groups()
            d, t = _num(done), _num(total) or _num(est)
            frac = (d / t) if d is not None and t else None
            if status == "finished":
                state["stream"] += 1
                frac = 1.0
            if frac is not None:
                overall = min(0.99, (min(state["stream"], streams_expected - 1) + frac) / streams_expected) if status != "finished" else min(0.99, state["stream"] / streams_expected)
                ctx.progress(overall, "downloading", None, _num(speed), _num(eta))
            else:
                ctx.progress(None, "downloading", None, _num(speed), _num(eta))
            return
        if line.startswith("BAIXAI_PP "):
            ctx.progress(0.99, "converting", line.split(" ", 2)[1])
            return
        if line.startswith("BAIXAI_FILE "):
            files.append(line[len("BAIXAI_FILE "):])
            return
        ctx.log(line)

    rc, tail = run_streaming(args, ctx, on_line)
    if rc != 0 or not files:
        raise classify("\n".join(tail), NAME) if rc != 0 else BaixaiError("no_output", "O yt-dlp terminou sem gerar arquivo.")
    out = [Path(f) for f in dict.fromkeys(files) if Path(f).is_file()]
    if not out:
        raise BaixaiError("no_output", "O yt-dlp terminou sem gerar arquivo.")
    return Result(files=out)
