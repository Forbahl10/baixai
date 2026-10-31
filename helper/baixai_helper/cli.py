"""Linha de comando: host, diagnóstico, instalação do host e utilitários de teste."""
from __future__ import annotations

import argparse
import json
import sys
import time

from . import APP_NAME, __version__, install_host, paths
from .errors import BaixaiError


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_doctor(args) -> int:
    from .service import Service

    svc = Service()
    st = svc.tools.status(True)
    dd = svc.settings.download_dir()
    host = install_host.status()
    info = {"app": APP_NAME, "version": __version__, "data_dir": str(paths.data_dir()), "download_dir": str(dd), "tools": st, "native_host": host}
    problems = []
    if not st["ytdlp"]["ok"]:
        problems.append("yt-dlp ausente")
    if not st["gallerydl"]["ok"]:
        problems.append("gallery-dl ausente")
    if not st["ffmpeg"]["ok"]:
        problems.append("FFmpeg ausente (MP3 e combinação de faixas indisponíveis)")
    if not st["js_runtime"]["ok"]:
        problems.append("Sem Deno/Node 22+ (alguns formatos do YouTube podem faltar)")
    if not host:
        problems.append("host Native Messaging não instalado")
    elif not all(h.get("valid") and h.get("path_exists") for h in host):
        problems.append("manifesto do host inválido ou aponta para um executável inexistente")
    if getattr(args, "json", False):
        _print({**info, "problems": problems})
        return 0 if not problems else 1

    def line(ok: bool, text: str) -> None:
        print(f"  [{'ok' if ok else '!!'}] {text}")

    print(f"{APP_NAME} {__version__}  (dados: {paths.data_dir()})")
    print(f"  Downloads em: {dd}")
    line(st["ytdlp"]["ok"], f"yt-dlp {st['ytdlp']['version'] or ''} ({st['ytdlp']['source'] or 'ausente'})")
    line(st["gallerydl"]["ok"], f"gallery-dl {st['gallerydl']['version'] or ''} ({st['gallerydl']['source'] or 'ausente'})")
    line(st["ffmpeg"]["ok"], f"FFmpeg {st['ffmpeg']['path'] or 'não encontrado'}")
    rt = st["js_runtime"]
    line(rt["ok"], f"Runtime JS: {rt['name']} {rt['version']}" if rt["ok"] else "Runtime JS (Deno ou Node 22+): não encontrado")
    for h in host:
        line(bool(h.get("valid") and h.get("path_exists")), f"Host Native Messaging ({h['browser']}): {h.get('manifest')}")
    if not host:
        line(False, "Host Native Messaging: não registrado")
    print("\nProblemas:" if problems else "\nTudo certo.", *("- " + p for p in problems), sep="\n")
    return 0 if not problems else 1


def cmd_analyze(args) -> int:
    from .service import Service

    try:
        _print(Service().analyze(args.url))
        return 0
    except BaixaiError as e:
        _print({"error": e.to_dict()})
        return 1


def cmd_download(args) -> int:
    """Baixa passando pela mesma fila persistente usada pela extensão (útil para testes reais)."""
    from .service import Service

    def emit(ev):
        if ev.get("event") == "job":
            j = ev["job"]
            pct = f"{j['progress'] * 100:5.1f}%" if j.get("progress") is not None else "  ...  "
            print(f"[{j['state']:<11}] {pct} {j.get('detail') or ''}", file=sys.stderr, flush=True)

    svc = Service(emit=emit)
    if args.dest:
        svc.settings.update({"download_dir": args.dest})
    svc.start()
    options = {}
    if args.height:
        options["height"] = args.height
    if args.container:
        options["container"] = args.container
    if args.audio_format:
        options["audio_format"] = args.audio_format
    if args.bitrate:
        options["mp3_bitrate"] = args.bitrate
    if args.image_format:
        options["image_format"] = args.image_format
    if args.items:
        options["items"] = [int(x) for x in args.items.split(",")]
    try:
        res = svc.queue.enqueue(args.url, args.mode, options, force=True)
    except BaixaiError as e:
        _print({"error": e.to_dict()})
        return 1
    jid = res["job"]["id"]
    svc.queue.wait_idle(args.timeout)
    job = svc.queue.list(5)
    final = next(j for j in job if j["id"] == jid)
    svc.shutdown()
    _print(final)
    return 0 if final["state"] == "done" else 1


def cmd_queue(args) -> int:
    from .store import Store

    for j in Store().list(100):
        print(f"{j['id']}  {j['state']:<11} {j['mode']:<6} {j['url']}")
    return 0


def cmd_install(args) -> int:
    import os

    exec_path = args.exec
    if not exec_path:
        exec_path = install_host.write_dev_wrapper(sys.executable)
    ids = args.extension_id or []
    _print({"manifests": install_host.install(exec_path, ids, args.browser or ["chrome"]), "exec": exec_path})
    return 0


def cmd_uninstall(args) -> int:
    _print({"removed": install_host.uninstall(args.browser or list(install_host.BROWSERS), args.purge_data)})
    return 0


def cmd_tools(args) -> int:
    from .service import Service

    svc = Service()
    if args.action == "status":
        _print(svc.tools.status(True))
    elif args.action == "check":
        _print(svc.cmd_tools_check_updates({}))
    elif args.action == "update-ytdlp":
        _print(svc.cmd_tools_update_ytdlp({}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="baixai-helper", description=f"{APP_NAME} — aplicativo auxiliar local")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    dd_ = sub.add_parser("doctor", help="diagnóstico"); dd_.add_argument("--json", action="store_true"); dd_.set_defaults(fn=cmd_doctor)
    a = sub.add_parser("analyze", help="analisa um link"); a.add_argument("url"); a.set_defaults(fn=cmd_analyze)
    d = sub.add_parser("download", help="baixa um link usando a fila (teste fora do Chrome)")
    d.add_argument("url"); d.add_argument("--mode", choices=["video", "audio", "image"], required=True)
    d.add_argument("--height", type=int); d.add_argument("--container", choices=["mp4", "original"])
    d.add_argument("--audio-format", choices=["mp3", "original"]); d.add_argument("--bitrate", type=int)
    d.add_argument("--image-format", choices=["original", "jpeg", "png"]); d.add_argument("--items")
    d.add_argument("--dest"); d.add_argument("--timeout", type=float, default=900); d.set_defaults(fn=cmd_download)
    sub.add_parser("queue", help="lista a fila").set_defaults(fn=cmd_queue)
    i = sub.add_parser("install-host", help="registra o host Native Messaging")
    i.add_argument("--extension-id", action="append", required=True, help="ID da extensão (repita para dev e produção)")
    i.add_argument("--browser", action="append", choices=list(install_host.BROWSERS)); i.add_argument("--exec", help="executável do host (padrão: wrapper de desenvolvimento)")
    i.set_defaults(fn=cmd_install)
    u = sub.add_parser("uninstall-host", help="remove o host Native Messaging")
    u.add_argument("--browser", action="append", choices=list(install_host.BROWSERS)); u.add_argument("--purge-data", action="store_true")
    u.set_defaults(fn=cmd_uninstall)
    t = sub.add_parser("tools", help="versões e atualização explícita"); t.add_argument("action", choices=["status", "check", "update-ytdlp"]); t.set_defaults(fn=cmd_tools)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except BaixaiError as e:
        print(f"Erro: {e.message}", file=sys.stderr)
        return 1
