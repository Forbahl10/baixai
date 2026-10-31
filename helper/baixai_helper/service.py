"""Roteador de comandos: junta fila, mecanismos, preferências e diagnóstico."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from . import PROTOCOL_VERSION, __version__, dialogs, platforms, tools
from .engines import direct, gallerydl, ytdlp
from .errors import BaixaiError
from .protocol import MAX_OUT, MessageTooLarge, encode_message
from .queue import ENGINES, JobQueue
from .settings import Settings
from .store import Store
from .urlsafe import validate_url

ANALYZERS = {"ytdlp": ytdlp.analyze, "gallerydl": gallerydl.analyze, "direct": direct.analyze}
BENIGN = {"no_media", "unsupported"}


class Service:
    def __init__(self, store: Store | None = None, emit: Callable[[dict], None] | None = None, engines: dict | None = None):
        self.store = store or Store()
        self.settings = Settings(self.store)
        self.tools = tools.Tools(self.settings)
        self.queue = JobQueue(self.store, self.settings, self.tools, emit=emit, engines=engines or ENGINES)

    def start(self) -> None:
        self.queue.start()

    def shutdown(self) -> None:
        self.queue.shutdown()

    # ------------------------------------------------------------------ análise
    def analyze(self, url: str) -> dict:
        checked = validate_url(url)
        det = platforms.detect(checked.url)
        settings = self.settings.all()
        if det is not None and not det.supported:
            raise BaixaiError("unsupported", det.note or "Esse tipo de link não é suportado.")
        order = det.engines if det else ("direct",)
        errors: list[BaixaiError] = []
        result: dict | None = None
        for eng in order:
            try:
                result = ANALYZERS[eng](checked.url, det, settings)
                break
            except BaixaiError as e:
                errors.append(e)
        if result is None:
            raise next((e for e in errors if e.code not in BENIGN), errors[0])
        result.update(url=checked.url, platform=det.platform if det else "direct",
                      platform_label=platforms.LABELS[det.platform if det else "direct"], content_kind=det.kind if det else "direct")
        result.setdefault("warnings", [])
        if det and det.note:
            result["warnings"].append(det.note)
        st = self.tools.status()
        if not st["ffmpeg"]["ok"] and ("audio" in result["modes"] or result.get("video", {}).get("formats", [{}])[0].get("needs_merge")):
            result["warnings"].append("FFmpeg não encontrado: MP3 e a combinação de vídeo e áudio ficarão indisponíveis até instalá-lo (veja Diagnóstico).")
        if (det and det.platform == "youtube") and not st["js_runtime"]["ok"]:
            result["warnings"].append("Nenhum runtime JavaScript (Deno ou Node.js 22+) foi encontrado; alguns formatos do YouTube podem não aparecer.")
        count = result.get("entry_count") or 0
        result["needs_confirmation"] = count > self.settings.get("playlist_confirm_threshold")
        result["defaults"] = {k: settings[k] for k in ("default_height", "default_container", "default_mp3_bitrate", "default_image_format")}
        return self._fit(result)

    @staticmethod
    def _fit(result: dict) -> dict:
        """Garante que a resposta caiba no limite de 1 MB do canal host → Chrome."""
        for _ in range(8):
            try:
                encode_message({"id": "x", "ok": True, "data": result})
                return result
            except MessageTooLarge:
                if result.get("entries"):
                    result["entries"] = result["entries"][: len(result["entries"]) // 2]
                    result["truncated_list"] = True
                elif result.get("image", {}).get("items"):
                    result["image"]["items"] = result["image"]["items"][: len(result["image"]["items"]) // 2]
                    result["truncated_list"] = True
                else:
                    break
        raise BaixaiError("too_large", f"A análise gerou uma resposta maior que {MAX_OUT // 1000} KB.")

    # ------------------------------------------------------------------ comandos
    def handle(self, cmd: str, p: dict):
        fn = getattr(self, f"cmd_{cmd}")
        return fn(p)

    def cmd_hello(self, p):
        return {"app": "Baixaí", "version": __version__, "protocol": PROTOCOL_VERSION, "platform": sys.platform,
                "download_dir": str(self.settings.download_dir()), "tools": self.tools.status(), "settings": self.settings.all(),
                "active_jobs": len(self.store.by_state(("waiting", "analyzing", "downloading", "converting")))}

    def cmd_analyze(self, p):
        return self.analyze(p["url"])

    def cmd_enqueue(self, p):
        return self.queue.enqueue(p["url"], p["mode"], p.get("options"), p.get("meta"), p.get("force", False))

    def cmd_enqueue_batch(self, p):
        out = []
        for e in p["entries"]:
            try:
                out.append({"url": e["url"], **self.queue.enqueue(e["url"], p["mode"], p.get("options"), e.get("meta"), p.get("force", False))})
            except BaixaiError as err:
                out.append({"url": e["url"], "error": err.to_dict()})
        return {"results": out}

    def cmd_list_jobs(self, p):
        return {"jobs": self.queue.list(p.get("limit", 200))}

    def cmd_cancel(self, p):
        return {"job": self.queue.cancel(p["id"])}

    def cmd_retry(self, p):
        return {"job": self.queue.retry(p["id"])}

    def cmd_remove(self, p):
        self.queue.remove(p["id"])
        return {}

    def cmd_clear_history(self, p):
        return {"removed": self.queue.clear_history()}

    def cmd_job_log(self, p):
        return {"lines": self.queue.logs(p["id"])}

    def cmd_reveal(self, p):
        job = self.store.get(p["id"])
        if not job:
            raise BaixaiError("not_found", "Trabalho não encontrado.")
        files = [Path(f) for f in job["files"]]
        target = next((f for f in files if f.exists()), None) or (Path(job["dest_dir"]) if job.get("dest_dir") else None)
        if target is None:
            raise BaixaiError("missing_file", "Este trabalho ainda não tem arquivos.")
        dialogs.reveal(target)
        return {}

    def cmd_get_settings(self, p):
        return {"settings": self.settings.all(), "download_dir": str(self.settings.download_dir())}

    def cmd_set_settings(self, p):
        s = self.settings.update(p["settings"])
        self.tools.invalidate()
        self.queue._wake()
        return {"settings": s, "download_dir": str(self.settings.download_dir())}

    def cmd_choose_folder(self, p):
        path = dialogs.choose_folder()
        if path:
            s = self.settings.update({"download_dir": path})
            return {"chosen": True, "settings": s, "download_dir": str(self.settings.download_dir())}
        return {"chosen": False}

    def cmd_tools_status(self, p):
        return {"tools": self.tools.status(p.get("refresh", False))}

    def cmd_tools_check_updates(self, p):
        return tools.check_updates(self.settings.all())

    def cmd_tools_update_ytdlp(self, p):
        res = tools.update_ytdlp(self.settings.all())
        self.tools.invalidate()
        return res
