"""Fila persistente de trabalhos: concorrência limitada, progresso, cancelamento e recuperação."""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from . import convert, platforms
from .engines import direct, gallerydl, ytdlp
from .engines.base import JobSpec, RunContext
from .errors import BaixaiError, Cancelled
from .friendly import classify
from .redact import redact
from .sanitize import safe_join, sanitize_filename, unique_path
from .store import ACTIVE, Store
from .urlsafe import validate_url

log = logging.getLogger("baixai.queue")
ENGINES = {"ytdlp": ytdlp, "gallerydl": gallerydl, "direct": direct}
MODES_BY_ENGINE = {"ytdlp": ("video", "audio"), "gallerydl": ("image",), "direct": ("image", "audio", "video")}
PUBLIC_FIELDS = ("id", "url", "platform", "engine", "mode", "options", "meta", "state", "stage", "progress", "speed", "eta", "detail",
                 "notes", "attempts", "created_at", "updated_at")


def public(job: dict) -> dict:
    out = {k: job.get(k) for k in PUBLIC_FIELDS}
    out["files"] = [{"name": Path(f).name, "path": f} for f in job.get("files", [])]
    out["error"] = ({"code": job["error_code"], "message": job["error_message"], "detail": job.get("error_detail")} if job.get("error_code") else None)
    return out


def normalize_options(mode: str, o: dict) -> dict:
    keep = {"video": ("height", "container", "engine"), "audio": ("audio_format", "mp3_bitrate", "engine"), "image": ("image_format", "items", "engine")}[mode]
    out = {k: o[k] for k in keep if k in o}
    if mode == "video":
        out.setdefault("container", "mp4")
    if mode == "audio":
        out.setdefault("audio_format", "mp3")
        if out["audio_format"] == "mp3":
            out.setdefault("mp3_bitrate", 192)
        else:
            out.pop("mp3_bitrate", None)
    if mode == "image":
        out.setdefault("image_format", "original")
        if "items" in out:
            out["items"] = sorted(set(out["items"]))
    return out


def dedupe_key(url: str, mode: str, options: dict) -> str:
    opts = {k: v for k, v in options.items() if k != "engine"}
    return hashlib.sha256(json.dumps([url, mode, opts], sort_keys=True).encode()).hexdigest()


class JobQueue:
    def __init__(self, store: Store, settings, tools, emit: Callable[[dict], None] | None = None, engines: dict | None = None):
        self.store, self.settings, self.tools = store, settings, tools
        self.emit = emit or (lambda ev: None)
        self.engines = engines or ENGINES
        self._cond = threading.Condition()
        self._cancels: dict[str, threading.Event] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._stopping = False
        self._dispatcher: threading.Thread | None = None
        self._last: dict[str, tuple[float, float]] = {}  # id -> (último evento, última gravação)

    # ------------------------------------------------------------- ciclo de vida
    def start(self) -> None:
        for j in self.store.by_state(("analyzing", "downloading", "converting")):
            self.store.update(j["id"], state="waiting", stage=None, detail="Retomando após reinício do aplicativo", speed=None, eta=None)
        self._dispatcher = threading.Thread(target=self._loop, name="dispatcher", daemon=True)
        self._dispatcher.start()

    def shutdown(self, timeout: float = 8.0) -> None:
        """Interrompe trabalhos em andamento; eles voltam a 'aguardando' e retomam no próximo início."""
        with self._cond:
            self._stopping = True
            for ev in self._cancels.values():
                ev.set()
            self._cond.notify_all()
        deadline = time.time() + timeout
        for t in list(self._threads.values()):
            t.join(max(0.1, deadline - time.time()))

    def wait_idle(self, timeout: float = 60.0) -> bool:
        """Utilitário (CLI e testes): espera não haver trabalhos ativos."""
        end = time.time() + timeout
        while time.time() < end:
            if not self.store.by_state(ACTIVE):
                return True
            time.sleep(0.1)
        return False

    def _wake(self) -> None:
        with self._cond:
            self._cond.notify_all()

    def _loop(self) -> None:
        while True:
            with self._cond:
                if self._stopping:
                    return
                slots = int(self.settings.get("max_concurrent")) - len(self._threads)
                if slots > 0:
                    for j in self.store.by_state(("waiting",))[:slots]:
                        if j["id"] in self._threads:
                            continue
                        self._set(j["id"], state="analyzing", stage="Preparando", error_code=None, error_message=None, error_detail=None,
                                  attempts=j["attempts"] + 1)
                        ev = threading.Event()
                        self._cancels[j["id"]] = ev
                        t = threading.Thread(target=self._run, args=(j["id"], ev), name=f"job-{j['id'][:6]}", daemon=True)
                        self._threads[j["id"]] = t
                        t.start()
                self._cond.wait(timeout=1.0)

    # ------------------------------------------------------------- API
    def enqueue(self, url: str, mode: str, options: dict | None = None, meta: dict | None = None, force: bool = False) -> dict:
        checked = validate_url(url)
        det = platforms.detect(checked.url)
        options = dict(options or {})
        if det is None:
            candidates: tuple[str, ...] = ("direct",)
            platform = "direct"
        elif not det.supported:
            raise BaixaiError("unsupported", det.note or "Esse tipo de link não é suportado.")
        else:
            candidates, platform = det.engines, det.platform
        engine = options.get("engine") or next((e for e in candidates if mode in MODES_BY_ENGINE[e]), None)
        if engine not in candidates or mode not in MODES_BY_ENGINE.get(engine, ()):
            raise BaixaiError("invalid_option", "Esse formato não está disponível para este link.")
        opts = normalize_options(mode, {**options, "engine": engine})
        key = dedupe_key(checked.url, mode, opts)
        existing = self.store.find_by_dedupe(key, ACTIVE)
        if existing:
            return {"job": public(existing), "duplicate": "active"}
        if not force:
            done = self.store.find_by_dedupe(key, ("done",))
            if done:
                return {"job": public(done), "duplicate": "done"}
        job = {
            "id": uuid.uuid4().hex[:16], "url": checked.url, "platform": platform, "engine": engine, "mode": mode, "options": opts,
            "meta": {k: v for k, v in (meta or {}).items()}, "dedupe_key": key, "state": "waiting", "attempts": 0,
        }
        self.store.insert(job)
        created = self.store.get(job["id"])
        self.emit({"event": "job", "job": public(created)})
        self._wake()
        return {"job": public(created), "duplicate": None}

    def list(self, limit: int = 200) -> list[dict]:
        return [public(j) for j in self.store.list(limit)]

    def cancel(self, job_id: str) -> dict:
        job = self._require(job_id)
        if job["state"] == "waiting" and job_id not in self._threads:
            self._cleanup_tmp(job_id)
            self._set(job_id, state="cancelled", stage=None, detail=None, speed=None, eta=None)
        elif job["state"] in ACTIVE:
            ev = self._cancels.get(job_id)
            if ev:
                ev.set()
        return public(self.store.get(job_id))

    def retry(self, job_id: str) -> dict:
        job = self._require(job_id)
        if job["state"] not in ("failed", "cancelled"):
            raise BaixaiError("invalid_state", "Só é possível repetir trabalhos que falharam ou foram cancelados.")
        self._set(job_id, state="waiting", stage=None, progress=None, detail=None, speed=None, eta=None, error_code=None, error_message=None, error_detail=None)
        self._wake()
        return public(self.store.get(job_id))

    def remove(self, job_id: str) -> None:
        job = self._require(job_id)
        if job["state"] in ACTIVE:
            self.cancel(job_id)
            t = self._threads.get(job_id)
            if t:
                t.join(10)
        self._cleanup_tmp(job_id)
        self.store.delete(job_id)
        self.emit({"event": "removed", "id": job_id})

    def clear_history(self) -> int:
        ids = self.store.delete_finished()
        for i in ids:
            self._cleanup_tmp(i)
        self.emit({"event": "cleared", "ids": ids})
        return len(ids)

    def logs(self, job_id: str) -> list[str]:
        self._require(job_id)
        return self.store.logs(job_id)

    # ------------------------------------------------------------- execução
    def _require(self, job_id: str) -> dict:
        job = self.store.get(job_id)
        if not job:
            raise BaixaiError("not_found", "Trabalho não encontrado.")
        return job

    def _set(self, job_id: str, **fields) -> dict:
        self.store.update(job_id, **fields)
        job = self.store.get(job_id)
        self.emit({"event": "job", "job": public(job)})
        return job

    def _tmp_dir(self, job_id: str) -> Path:
        return self.settings.download_dir() / ".baixai-tmp" / job_id

    def _cleanup_tmp(self, job_id: str) -> None:
        shutil.rmtree(self._tmp_dir(job_id), ignore_errors=True)
        parent = self.settings.download_dir() / ".baixai-tmp"
        try:
            parent.rmdir()
        except OSError:
            pass

    def _make_ctx(self, job_id: str, cancel: threading.Event) -> RunContext:
        def on_progress(fraction, stage, detail, speed, eta):
            now = time.time()
            last_ev, last_db = self._last.get(job_id, (0.0, 0.0))
            state = "converting" if stage == "converting" else "downloading"
            current = self.store.get(job_id)
            changed = current and current["state"] != state
            if not changed and now - last_ev < 0.4:
                return
            fields = dict(state=state, stage=stage, progress=fraction, detail=detail, speed=speed, eta=eta)
            if changed or now - last_db >= 1.0:
                self.store.update(job_id, **fields)
                last_db = now
            job = {**(current or {}), **fields}
            self._last[job_id] = (now, last_db)
            self.emit({"event": "job", "job": public(job)})

        def on_log(line: str):
            line = redact(line, max_len=400)
            if line.strip():
                self.store.add_log(job_id, line)

        return RunContext(cancel, on_progress, on_log, self.settings.all(), self.tools)

    def _run(self, job_id: str, cancel: threading.Event) -> None:
        try:
            job = self.store.get(job_id)
            if job is None:
                return
            spec = JobSpec(job["id"], job["url"], job["platform"], job["engine"], job["mode"], job["options"], job["meta"])
            ctx = self._make_ctx(job_id, cancel)
            if cancel.is_set():
                raise Cancelled()
            validate_url(spec.url)  # revalida (DNS pode ter mudado)
            tmp = self._tmp_dir(job_id)
            tmp.mkdir(parents=True, exist_ok=True)
            self._set(job_id, state="downloading", stage="downloading", progress=None, detail=None)
            result = self.engines[spec.engine].download(spec, tmp, ctx)
            files, notes = self._postprocess(spec, result.files, ctx)
            final, dest = self._finalize(spec, files)
            self._cleanup_tmp(job_id)
            self._set(job_id, state="done", stage=None, progress=1.0, speed=None, eta=None, detail=None, files=[str(p) for p in final],
                      notes=[*result.notes, *notes], dest_dir=str(dest))
        except Cancelled:
            if self._stopping:
                self._set(job_id, state="waiting", stage=None, detail="Interrompido ao encerrar; será retomado", speed=None, eta=None)
            else:
                self._cleanup_tmp(job_id)  # primeiro limpa, depois publica o estado final
                self._set(job_id, state="cancelled", stage=None, speed=None, eta=None, detail=None)
        except BaixaiError as e:
            self._fail(job_id, e)
        except Exception as e:  # nunca derruba o aplicativo
            log.exception("erro inesperado no trabalho %s", job_id)
            self._fail(job_id, classify(f"{type(e).__name__}: {e}"))
        finally:
            with self._cond:
                self._threads.pop(job_id, None)
                self._cancels.pop(job_id, None)
                self._last.pop(job_id, None)
                self._cond.notify_all()

    def _fail(self, job_id: str, err: BaixaiError) -> None:
        self.store.add_log(job_id, redact(f"ERRO {err.code}: {err.message} {err.detail or ''}", max_len=500))
        self._set(job_id, state="failed", stage=None, speed=None, eta=None, error_code=err.code, error_message=err.message, error_detail=err.detail)

    def _postprocess(self, spec: JobSpec, files: list[Path], ctx: RunContext) -> tuple[list[Path], list[str]]:
        notes: list[str] = []
        out: list[Path] = []
        fmt = spec.options.get("image_format", "original")
        for f in files:
            ctx.check()
            if spec.mode == "image" and fmt != "original" and gallerydl.kind_of(f.suffix) == "image":
                ctx.progress(None, "converting", f.name)
                f, n = convert.convert_image(f, fmt)
                notes += [x for x in n if x not in notes]
            elif spec.engine == "direct" and spec.mode == "audio" and spec.options.get("audio_format", "mp3") == "mp3" and f.suffix.lower() != ".mp3":
                ctx.progress(None, "converting", f.name)
                f = convert.to_mp3(f, int(spec.options.get("mp3_bitrate", 192)), ctx)
            out.append(f)
        return out, notes

    def _finalize(self, spec: JobSpec, files: list[Path]) -> tuple[list[Path], Path]:
        s = self.settings.all()
        parts: list[str] = []
        if s["organize_by_platform"]:
            parts.append(platforms.LABELS.get(spec.platform, spec.platform))
        author = (spec.meta or {}).get("author")
        if s["organize_by_author"] and author:
            parts.append(author)
        dest = safe_join(self.settings.download_dir(), *parts)
        dest.mkdir(parents=True, exist_ok=True)
        final: list[Path] = []
        for f in files:
            target = unique_path(dest / sanitize_filename(f.name))
            shutil.move(str(f), str(target))
            final.append(target)
        return final, dest
