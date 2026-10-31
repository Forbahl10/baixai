"""Uso pelo terminal: `baixai "LINK"` analisa, escolhe bons padrões e baixa, com progresso na tela."""
from __future__ import annotations

import sys
import threading

from .errors import BaixaiError
from .service import Service

DONE_STATES = ("done", "failed", "cancelled")
STATE_PT = {"waiting": "aguardando", "analyzing": "analisando", "downloading": "baixando", "converting": "convertendo",
            "done": "concluído", "cancelled": "cancelado", "failed": "falhou"}


def _fmt_size(bps: float | None) -> str:
    if not bps:
        return ""
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bps < 1024 or unit == "GB/s":
            return f"{bps:.0f} {unit}" if unit == "B/s" else f"{bps:.1f} {unit}"
        bps /= 1024
    return ""


def _fmt_eta(sec: float | None) -> str:
    if sec is None:
        return ""
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


class Progress:
    """Mostra o andamento: uma linha que se atualiza em terminais, ou linhas espaçadas quando a saída é redirecionada."""

    def __init__(self) -> None:
        self.tty = sys.stderr.isatty()
        self.lock = threading.Lock()
        self.labels: dict[str, str] = {}
        self.last_state: dict[str, str] = {}
        self.last_pct: dict[str, int] = {}
        self.line_open = False

    def label(self, job_id: str, text: str) -> None:
        self.labels[job_id] = text

    def __call__(self, ev: dict) -> None:
        if ev.get("event") != "job":
            return
        j = ev["job"]
        jid, state = j["id"], j["state"]
        name = self.labels.get(jid, j["url"])
        if len(name) > 48:
            name = name[:45] + "..."
        pct = j.get("progress")
        extra = " ".join(x for x in (f"{pct * 100:5.1f}%" if pct is not None else "", _fmt_size(j.get("speed")), f"falta {_fmt_eta(j.get('eta'))}" if j.get("eta") else "") if x)
        text = f"{name}  [{STATE_PT.get(state, state)}] {extra}".rstrip()
        with self.lock:
            if self.tty:
                end = "\n" if state in DONE_STATES else ""
                sys.stderr.write("\r\033[K" + text + end)
                sys.stderr.flush()
                self.line_open = state not in DONE_STATES
            else:
                bucket = int((pct or 0) * 10)
                if state != self.last_state.get(jid) or (state == "downloading" and bucket != self.last_pct.get(jid)):
                    print(text, file=sys.stderr, flush=True)
                self.last_pct[jid] = bucket
            self.last_state[jid] = state

    def break_line(self) -> None:
        with self.lock:
            if self.tty and self.line_open:
                sys.stderr.write("\n")
                self.line_open = False


def _ask(question: str) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        return input(f"{question} [s/N] ").strip().lower() in ("s", "sim", "y", "yes")
    except EOFError:
        return False


def _parse_items(text: str | None) -> list[int] | None:
    if not text:
        return None
    try:
        return sorted({int(x) for x in text.split(",") if x.strip()})
    except ValueError:
        raise BaixaiError("invalid_option", "--itens deve ser uma lista de números separados por vírgula, ex.: 1,3,5") from None


def plan(svc: Service, url: str, args) -> list[tuple[str, str, dict, str]]:
    """Analisa o link e devolve a lista de (url, modo, opções, rótulo) a enfileirar."""
    a = svc.analyze(url)
    modes = a["modes"]
    for w in a.get("warnings", []):
        print(f"Aviso: {w}", file=sys.stderr)
    if args.audio:
        mode = "audio"
    elif args.imagem:
        mode = "image"
    else:
        mode = next((m for m in ("video", "image", "audio") if m in modes), "")
    if mode not in modes:
        disponiveis = ", ".join({"video": "vídeo", "audio": "áudio (-a)", "image": "imagem (-i)"}[m] for m in modes) or "nenhum"
        raise BaixaiError("invalid_option", f"Esse link não oferece {'áudio' if mode == 'audio' else 'imagem' if mode == 'image' else 'vídeo'}. Disponível: {disponiveis}.")
    d = a["defaults"]
    opts: dict = {}
    if mode == "video":
        opts = {"height": args.qualidade or d["default_height"], "container": "original" if args.original else "mp4"}
    elif mode == "audio":
        opts = {"audio_format": "original" if args.original else "mp3", "mp3_bitrate": args.bitrate or d["default_mp3_bitrate"]}
    else:
        opts = {"image_format": args.formato_imagem or ("original" if args.original else d["default_image_format"])}
    title = a.get("title") or url

    entries = a.get("entries") or []
    if entries:  # lista de reprodução / álbum: cada item vira um trabalho
        wanted = _parse_items(args.itens)
        chosen = [e for e in entries if wanted is None or e["index"] in wanted]
        if not chosen:
            raise BaixaiError("invalid_option", "Nenhum item corresponde a --itens.")
        if wanted is None and not args.tudo:
            if not _ask(f"'{title}' é uma lista com {len(entries)} itens. Baixar todos?"):
                raise BaixaiError("needs_confirmation", f"É uma lista com {len(entries)} itens. Use --tudo para baixar todos ou --itens 1,3,5 para escolher.")
        return [(e["url"], mode, dict(opts), e.get("title") or e["url"]) for e in chosen]

    items = (a.get("image") or {}).get("items") or []
    if mode == "image" and items:  # galeria de imagens: uma tarefa com vários itens
        wanted = _parse_items(args.itens)
        if wanted:
            opts["items"] = wanted
        elif a.get("needs_confirmation") and not args.tudo:
            if not _ask(f"A galeria tem {len(items)} imagens. Baixar todas?"):
                raise BaixaiError("needs_confirmation", f"A galeria tem {len(items)} imagens. Use --tudo para baixar todas ou --itens 1,3,5 para escolher.")
    return [(a["url"], mode, opts, title)]


def run(args) -> int:
    progress = Progress()
    svc = Service(emit=progress)
    old_dir = svc.settings.get("download_dir")
    if args.pasta:
        svc.settings.update({"download_dir": args.pasta})  # vale só para esta execução (restaurado ao final)
    st = svc.tools.status()
    if not st["ffmpeg"]["ok"]:
        print("Dica: o FFmpeg não foi encontrado (MP3 e vídeo em alta qualidade precisam dele). Rode:  baixai tools install-deps", file=sys.stderr)
    svc.start()
    ids: list[str] = []
    failed_plan = False
    try:
        for url in args.urls:
            try:
                for u, mode, opts, label in plan(svc, url, args):
                    res = svc.queue.enqueue(u, mode, opts, force=True)
                    jid = res["job"]["id"]
                    progress.label(jid, label)
                    ids.append(jid)
            except BaixaiError as e:
                failed_plan = True
                print(f"Erro ({url}): {e.message}", file=sys.stderr)
        if not ids:
            return 1
        try:
            while not svc.queue.wait_idle(0.5):
                pass
        except KeyboardInterrupt:
            progress.break_line()
            print("Cancelando...", file=sys.stderr)
            for jid in ids:
                try:
                    svc.queue.cancel(jid)
                except BaixaiError:
                    pass
            svc.queue.wait_idle(20)
            return 130
        progress.break_line()
        by_id = {j["id"]: j for j in svc.queue.list(max(50, len(ids) * 2))}
        ok = True
        for jid in ids:
            j = by_id.get(jid)
            if j is None:
                continue
            if j["state"] == "done":
                for f in j["files"]:
                    print(f"Pronto: {f['path']}")
                for n in j.get("notes") or []:
                    print(f"  Obs.: {n}")
            else:
                ok = False
                err = j.get("error") or {}
                print(f"Falhou: {progress.labels.get(jid, j['url'])}\n  {err.get('message') or STATE_PT.get(j['state'], j['state'])}", file=sys.stderr)
                if args.detalhes and err.get("detail"):
                    print("  " + str(err["detail"]).strip().replace("\n", "\n  "), file=sys.stderr)
        return 0 if ok and not failed_plan else 1
    finally:
        if args.pasta:
            try:
                svc.settings.update({"download_dir": old_dir or ""})
            except BaixaiError:
                pass
        svc.shutdown()
