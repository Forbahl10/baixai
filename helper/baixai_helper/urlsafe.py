"""Validação de URLs (anti-SSRF) e cliente HTTP que valida cada redirecionamento.

Regras: somente http/https, sem credenciais embutidas, sem hosts locais/privados,
todos os endereços resolvidos precisam ser públicos. O download direto usa uma
conexão "fixada" no IP validado, o que evita DNS rebinding entre a checagem e o uso.
"""
from __future__ import annotations

import http.client
import ipaddress
import os
import re
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

from .errors import BaixaiError

MAX_URL_LEN = 2048
_CONTROL = re.compile(r"[\x00-\x20\x7f]")
_LOCAL_SUFFIXES = (".local", ".localhost", ".internal", ".localdomain", ".lan", ".home", ".corp", ".intranet", ".home.arpa")
USER_AGENT = "Mozilla/5.0 (compatible; Baixai/0.1; +local)"


def allow_private() -> bool:
    """Somente para testes automatizados com servidor local. Nunca definido pela extensão."""
    return os.environ.get("BAIXAI_ALLOW_PRIVATE_NETWORK") == "1"


@dataclass(frozen=True)
class CheckedUrl:
    url: str
    scheme: str
    host: str
    port: int
    path_q: str


def _reject(code: str, msg: str) -> BaixaiError:
    return BaixaiError(code, msg)


def _ip_is_public(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def validate_url(raw: str, *, resolve: bool = True) -> CheckedUrl:
    if not isinstance(raw, str):
        raise _reject("invalid_url", "Endereço inválido.")
    raw = raw.strip()
    if not raw or len(raw) > MAX_URL_LEN:
        raise _reject("invalid_url", "Endereço vazio ou longo demais.")
    if _CONTROL.search(raw):
        raise _reject("invalid_url", "O endereço contém espaços ou caracteres de controle.")
    try:
        parts = urlsplit(raw)
        port = parts.port
    except ValueError:
        raise _reject("invalid_url", "Endereço inválido.") from None
    if parts.scheme.lower() not in ("http", "https"):
        raise _reject("invalid_scheme", "Somente links http:// ou https:// são aceitos.")
    if parts.username is not None or parts.password is not None:
        raise _reject("invalid_url", "Links com usuário e senha embutidos não são aceitos.")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise _reject("invalid_url", "O endereço não tem um servidor válido.")
    scheme = parts.scheme.lower()
    default_port = 443 if scheme == "https" else 80
    if port is not None and port not in (80, 443) and not allow_private():
        raise _reject("blocked_port", "Somente as portas padrão (80 e 443) são aceitas.")
    port = port or default_port

    literal: ipaddress._BaseAddress | None = None
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        pass
    if literal is None:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            raise _reject("invalid_url", "Nome de servidor inválido.") from None
        if "." not in host or host.endswith(_LOCAL_SUFFIXES) or host == "localhost":
            if not allow_private():
                raise _reject("blocked_host", "Endereços da rede local não são permitidos.")

    if resolve and not allow_private():
        addrs = _resolve(host, port)
        for ip in addrs:
            if not _ip_is_public(ip):
                raise _reject("blocked_host", "Esse endereço aponta para a rede local ou para um destino não público.")
    elif literal is not None and not allow_private() and not _ip_is_public(literal):
        raise _reject("blocked_host", "Endereços da rede local não são permitidos.")

    netloc = host if ":" not in host else f"[{host}]"
    if port != default_port:
        netloc += f":{port}"
    path = parts.path or "/"
    clean = urlunsplit((scheme, netloc, path, parts.query, ""))
    path_q = path + (f"?{parts.query}" if parts.query else "")
    return CheckedUrl(clean, scheme, host, port, path_q)


def _resolve(host: str, port: int) -> list[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise _reject("dns_failed", "Não foi possível resolver o endereço (verifique a conexão e o link).") from None
    out: list[ipaddress._BaseAddress] = []
    for info in infos:
        addr = info[4][0].split("%")[0]
        out.append(ipaddress.ip_address(addr))
    if not out:
        raise _reject("dns_failed", "Não foi possível resolver o endereço.")
    return out


# ---------------------------------------------------------------- HTTP seguro
class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, port, ip, timeout):
        self._ctx = ssl.create_default_context()
        super().__init__(host, port, timeout=timeout, context=self._ctx)
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._ctx.wrap_socket(sock, server_hostname=self.host)


class SafeResponse:
    def __init__(self, conn, resp, final_url: str):
        self._conn, self._resp, self.final_url = conn, resp, final_url
        self.status = resp.status
        self.headers = resp.headers

    def read(self, n: int = 65536) -> bytes:
        return self._resp.read(n)

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


def safe_open(url: str, *, method: str = "GET", headers: dict | None = None, timeout: float = 30, max_redirects: int = 5) -> SafeResponse:
    """Abre `url` validando cada salto de redirecionamento."""
    current = url
    for _ in range(max_redirects + 1):
        checked = validate_url(current, resolve=False)
        ip = _pick_ip(checked)
        cls = _PinnedHTTPS if checked.scheme == "https" else _PinnedHTTP
        conn = cls(checked.host, checked.port, ip, timeout)
        hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "identity", **(headers or {})}
        try:
            conn.request(method, checked.path_q, headers=hdrs)
            resp = conn.getresponse()
        except (OSError, http.client.HTTPException) as e:
            conn.close()
            raise BaixaiError("network", "Falha de conexão com o servidor.", detail=type(e).__name__, retryable=True) from None
        if resp.status in (301, 302, 303, 307, 308):
            loc = resp.getheader("Location")
            conn.close()
            if not loc:
                raise BaixaiError("bad_redirect", "Redirecionamento inválido.")
            current = urljoin(checked.url, loc)
            continue
        return SafeResponse(conn, resp, checked.url)
    raise BaixaiError("too_many_redirects", "Redirecionamentos demais.")


def _pick_ip(c: CheckedUrl) -> str:
    if allow_private():
        return c.host if _is_ip(c.host) else socket.getaddrinfo(c.host, c.port, type=socket.SOCK_STREAM)[0][4][0]
    addrs = _resolve(c.host, c.port)
    for ip in addrs:
        if not _ip_is_public(ip):
            raise _reject("blocked_host", "Esse endereço aponta para a rede local ou para um destino não público.")
    return str(addrs[0])


def _is_ip(h: str) -> bool:
    try:
        ipaddress.ip_address(h)
        return True
    except ValueError:
        return False
