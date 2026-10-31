"""Erros do aplicativo, sempre com código estável e mensagem em português."""
from __future__ import annotations


class BaixaiError(Exception):
    def __init__(self, code: str, message: str, *, detail: str | None = None, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.retryable = retryable

    def to_dict(self) -> dict:
        d = {"code": self.code, "message": self.message, "retryable": self.retryable}
        if self.detail:
            d["detail"] = self.detail
        return d


class ProtocolError(BaixaiError):
    pass


class Cancelled(Exception):
    """Lançada quando o trabalho foi cancelado (ou interrompido pelo encerramento)."""
