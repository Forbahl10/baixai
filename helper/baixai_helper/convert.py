"""Conversões locais: imagens (Pillow) e áudio direto → MP3 (FFmpeg)."""
from __future__ import annotations

import os
from pathlib import Path

from .engines.base import RunContext, run_streaming
from .errors import BaixaiError
from .friendly import classify
from .tools import ffmpeg_path

JPEG_QUALITY = 92


def convert_image(src: Path, fmt: str) -> tuple[Path, list[str]]:
    """Converte para 'jpeg' ou 'png'. Em caso de falha, mantém o original e avisa."""
    notes: list[str] = []
    if fmt not in ("jpeg", "png"):
        return src, notes
    target_ext = ".jpg" if fmt == "jpeg" else ".png"
    if src.suffix.lower() in ((".jpg", ".jpeg", ".jfif") if fmt == "jpeg" else (".png",)):
        return src, notes  # já está no formato pedido
    try:
        from PIL import Image
    except ImportError:
        return src, ["Conversão indisponível (Pillow ausente); o arquivo original foi mantido."]
    dst = src.with_suffix(target_ext)
    try:
        with Image.open(src) as im:
            if getattr(im, "n_frames", 1) > 1:
                notes.append("Imagem animada: apenas o primeiro quadro foi convertido.")
            im.seek(0)
            has_alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
            if fmt == "jpeg":
                rgba = im.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.getchannel("A"))
                bg.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)
                if has_alpha:
                    notes.append("A transparência foi substituída por fundo branco ao converter para JPEG.")
            else:
                (im if im.mode in ("RGB", "RGBA", "L", "LA", "P") else im.convert("RGBA")).save(dst, "PNG", optimize=True)
    except Exception:
        dst.unlink(missing_ok=True)
        return src, [f"Não foi possível converter {src.suffix.lstrip('.').upper()} para {fmt.upper()}; o original foi mantido."]
    src.unlink(missing_ok=True)
    return dst, notes


def to_mp3(src: Path, bitrate: int, ctx: RunContext) -> Path:
    ff = ffmpeg_path(ctx.settings)
    if not ff:
        raise classify("ffmpeg not found")
    dst = src.with_suffix(".mp3")
    if dst == src:
        return src
    cmd = [ff, "-nostdin", "-y", "-i", str(src), "-vn", "-map_metadata", "0", "-codec:a", "libmp3lame", "-b:a", f"{bitrate}k", str(dst)]
    rc, tail = run_streaming(cmd, ctx, lambda line: ctx.log(line))
    if rc != 0 or not dst.exists():
        dst.unlink(missing_ok=True)
        raise BaixaiError("convert_failed", "A conversão para MP3 falhou.", detail="\n".join(tail[-2:])[:300])
    src.unlink(missing_ok=True)
    return dst
