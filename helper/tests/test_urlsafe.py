import socket

import pytest

from baixai_helper.errors import BaixaiError
from baixai_helper.urlsafe import validate_url


def fake_dns(monkeypatch, ip):
    def gai(host, port, type=0, **kw):
        fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(fam, socket.SOCK_STREAM, 6, "", (ip, port))]
    monkeypatch.setattr(socket, "getaddrinfo", gai)


@pytest.mark.parametrize("url", [
    "ftp://example.com/x", "file:///etc/passwd", "javascript:alert(1)", "data:text/html,hi", "//example.com/x", "example.com/x", "",
    "https://user:pass@example.com/", "https://example.com:8080/x", "https://exa mple.com/", "https://example.com/\nx", "http://",
    "https://localhost/x", "https://foo.local/x", "https://intranet/x", "https://router.lan/", "https://x.internal/",
])
def test_rejeita_urls_invalidas(url, monkeypatch):
    fake_dns(monkeypatch, "93.184.216.34")
    with pytest.raises(BaixaiError):
        validate_url(url)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "172.16.0.1", "169.254.169.254", "100.64.0.1", "0.0.0.0", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1", "224.0.0.1"])
def test_rejeita_enderecos_nao_publicos_resolvidos(ip, monkeypatch):
    fake_dns(monkeypatch, ip)
    with pytest.raises(BaixaiError) as e:
        validate_url("https://www.youtube.com/watch?v=abc")
    assert e.value.code == "blocked_host"


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://[::1]/", "http://2130706433/", "http://0x7f.1/", "http://169.254.169.254/latest/meta-data/", "http://192.168.0.1/"])
def test_rejeita_ip_literal_e_formas_ofuscadas(url):
    # sem mock de DNS: o próprio getaddrinfo interpreta as formas curtas/hex/decimais
    with pytest.raises(BaixaiError):
        validate_url(url)


def test_aceita_url_publica_e_normaliza(monkeypatch):
    fake_dns(monkeypatch, "93.184.216.34")
    c = validate_url("  HTTPS://WWW.YouTube.com/watch?v=abc#frag ")
    assert c.url == "https://www.youtube.com/watch?v=abc" and c.host == "www.youtube.com" and c.port == 443


def test_url_longa_demais(monkeypatch):
    fake_dns(monkeypatch, "93.184.216.34")
    with pytest.raises(BaixaiError):
        validate_url("https://example.com/" + "a" * 3000)


def test_redirecionamento_para_rede_local_e_bloqueado(monkeypatch):
    """safe_open valida cada salto: um 302 para 127.0.0.1 deve ser recusado."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()
        def log_message(self, *a): pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    from baixai_helper import urlsafe
    # 1º salto permitido (servidor de teste em loopback); o destino do redirect é público/privado real e deve cair na validação
    monkeypatch.setenv("BAIXAI_ALLOW_PRIVATE_NETWORK", "1")
    real_validate = urlsafe.validate_url

    def strict_for_redirect(raw, resolve=True):
        if "169.254" in raw:
            monkeypatch.delenv("BAIXAI_ALLOW_PRIVATE_NETWORK")
        return real_validate(raw, resolve=resolve)

    monkeypatch.setattr(urlsafe, "validate_url", strict_for_redirect)
    with pytest.raises(BaixaiError) as e:
        urlsafe.safe_open(f"http://127.0.0.1:{srv.server_address[1]}/x")
    assert e.value.code == "blocked_host"
    srv.shutdown()
