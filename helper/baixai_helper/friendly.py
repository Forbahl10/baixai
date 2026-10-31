"""Traduz erros técnicos dos mecanismos em mensagens úteis, sem dados sensíveis."""
from __future__ import annotations

from .errors import BaixaiError
from .redact import redact

_RULES: list[tuple[tuple[str, ...], str, str, bool]] = [
    (("ffmpeg is not installed", "ffmpeg not found", "ffprobe and ffmpeg not found", "requires ffmpeg", "ffmpeg or avconv"),
     "ffmpeg_missing", "O FFmpeg não foi encontrado. Ele é necessário para combinar faixas e converter. Veja o Diagnóstico.", False),
    (("sign in to confirm", "confirm you’re not a bot", "confirm you're not a bot"), "auth_required",
     "A plataforma pediu confirmação de que você não é um robô. Tente novamente mais tarde; o MVP não usa login.", False),
    (("login required", "log in", "login is required", "requires authentication", "private video", "this post is private", "need to log in", "restricted video", "age-restricted", "age restricted", "nsfw", "protected tweet", "authentication", "cookies", "401", "403", "unauthorized", "forbidden"),
     "auth_required", "Este conteúdo exige login ou não é público. O MVP baixa apenas conteúdo público, sem usar sua conta.", False),
    (("video unavailable", "this video is not available", "has been removed", "no longer available", "does not exist", "page not found", "http error 404", "404 not found", "deleted"),
     "unavailable", "O conteúdo não está disponível (pode ter sido removido ou o link está incorreto).", False),
    (("not available in your country", "geo", "blocked it in your country"), "geo_blocked", "O conteúdo não está disponível na sua região.", False),
    (("unsupported url",), "unsupported", "Esse link não é suportado pelo mecanismo de download.", False),
    (("no video could be found", "there is no video", "no media found", "no results", "no extractor"), "no_media", "Não foi encontrada mídia nesse link para este mecanismo.", False),
    (("drm",), "drm", "O conteúdo é protegido por DRM e não pode ser baixado por este aplicativo.", False),
    (("429", "too many requests", "rate limit", "rate-limit"), "rate_limited", "A plataforma limitou as requisições. Aguarde alguns minutos e tente de novo.", True),
    (("timed out", "timeout", "temporary failure", "connection reset", "connection refused", "network is unreachable", "name or service not known", "getaddrinfo", "unable to download", "ssl"),
     "network", "Falha de rede ao falar com a plataforma. Verifique a conexão e tente novamente.", True),
    (("no space left", "disk full"), "disk_full", "Não há espaço suficiente no disco.", False),
    (("permission denied", "read-only file system"), "permission", "Sem permissão para gravar na pasta de destino.", False),
]


def classify(text: str, engine: str = "") -> BaixaiError:
    low = (text or "").lower()
    # Considera apenas a parte relevante (últimas linhas de erro) para o detalhe.
    err_lines = [ln for ln in (text or "").splitlines() if "error" in ln.lower() or "falha" in ln.lower()]
    detail = redact(err_lines[-1] if err_lines else (text or "").strip().splitlines()[-1] if (text or "").strip() else "", max_len=300)
    for needles, code, msg, retry in _RULES:
        if any(n in low for n in needles):
            return BaixaiError(code, msg, detail=detail or None, retryable=retry)
    return BaixaiError("engine_error", "O mecanismo de download não conseguiu concluir. Veja o log para detalhes.", detail=detail or None, retryable=True)
