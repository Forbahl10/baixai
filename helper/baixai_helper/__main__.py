"""Ponto de entrada: `python -m baixai_helper` ou o executável empacotado."""
from __future__ import annotations

import sys


def _run_engine(name: str, args: list[str]) -> int:
    """Executa yt-dlp/gallery-dl embutidos (usado quando o aplicativo está empacotado)."""
    if name == "yt-dlp":
        import yt_dlp

        yt_dlp.main(args)
        return 0
    if name == "gallery-dl":
        import gallery_dl

        sys.argv = ["gallery-dl", *args]
        return gallery_dl.main() or 0
    return 2


def main() -> int:
    argv = sys.argv[1:]
    if len(argv) >= 2 and argv[0] == "--engine":
        return _run_engine(argv[1], argv[2:])
    # O Chrome chama o host com a origem da extensão como primeiro argumento.
    if argv and argv[0].startswith("chrome-extension://"):
        from .host import main as host_main

        return host_main(argv[0])
    if argv and argv[0] == "host":  # modo desenvolvimento: baixai-host <origem>
        from .host import main as host_main

        return host_main(argv[1] if len(argv) > 1 else None)
    from .cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
