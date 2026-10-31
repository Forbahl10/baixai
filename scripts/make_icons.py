"""Gera os ícones da extensão (identidade própria: seta de download em quadrado arredondado)."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "extension" / "public" / "icons"
OUT.mkdir(parents=True, exist_ok=True)
S = 512


def master() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    px = grad.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S)
            px[x, y] = (int(11 + (22 - 11) * t), int(122 + (170 - 122) * t), int(117 + (160 - 117) * t), 255)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    w = int(S * 0.085)
    cx = S // 2
    d.line((cx, int(S * 0.2), cx, int(S * 0.58)), fill="white", width=w)
    d.line((int(S * 0.33), int(S * 0.43), cx, int(S * 0.62)), fill="white", width=w)
    d.line((int(S * 0.67), int(S * 0.43), cx, int(S * 0.62)), fill="white", width=w)
    d.line((int(S * 0.24), int(S * 0.76), int(S * 0.76), int(S * 0.76)), fill="white", width=w)
    for r in (int(w / 2),):  # pontas arredondadas
        for (x, y) in ((cx, int(S * 0.2)), (int(S * 0.33), int(S * 0.43)), (int(S * 0.67), int(S * 0.43)), (cx, int(S * 0.62)), (int(S * 0.24), int(S * 0.76)), (int(S * 0.76), int(S * 0.76))):
            d.ellipse((x - r, y - r, x + r, y + r), fill="white")
    return img


m = master()
for size in (16, 32, 48, 128):
    m.resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png")
print("ícones gerados em", OUT)
