import io
import json
import struct

import pytest

from baixai_helper.errors import ProtocolError
from baixai_helper.protocol import MAX_IN, MAX_OUT, MessageTooLarge, encode_message, read_message, validate_request


def frame(obj):
    d = json.dumps(obj).encode()
    return struct.pack("=I", len(d)) + d


def test_roundtrip_utf8():
    msg = {"id": "a1", "cmd": "analyze", "payload": {"url": "https://x.com/ação"}}
    assert read_message(io.BytesIO(encode_message(msg))) == msg


def test_eof_retorna_none_e_truncada_falha():
    assert read_message(io.BytesIO(b"")) is None
    with pytest.raises(ProtocolError):
        read_message(io.BytesIO(struct.pack("=I", 50) + b"{}"))
    with pytest.raises(ProtocolError):
        read_message(io.BytesIO(b"\x01\x00"))


def test_json_invalido_e_nao_objeto():
    for payload in (b"nao json", b"[1,2]", b"\xff\xfe"):
        with pytest.raises(ProtocolError):
            read_message(io.BytesIO(struct.pack("=I", len(payload)) + payload))


def test_mensagem_de_entrada_grande_e_descartada_sem_travar():
    n = MAX_IN + 10
    stream = io.BytesIO(struct.pack("=I", n) + b"a" * n + frame({"id": "ok", "cmd": "hello"}))
    with pytest.raises(ProtocolError) as e:
        read_message(stream)
    assert e.value.code == "message_too_large"
    assert read_message(stream)["id"] == "ok"  # o fluxo continua alinhado


def test_saida_acima_do_limite_do_chrome():
    with pytest.raises(MessageTooLarge):
        encode_message({"x": "a" * MAX_OUT})


@pytest.mark.parametrize("msg", [
    {"cmd": "nope"}, {"cmd": 5}, {"id": "a b", "cmd": "hello"}, {"id": "a", "cmd": "hello", "extra": 1},
    {"cmd": "analyze", "payload": {}}, {"cmd": "analyze", "payload": {"url": 5}}, {"cmd": "analyze", "payload": {"url": "x", "y": 1}},
    {"cmd": "enqueue", "payload": {"url": "https://a.com", "mode": "zip"}},
    {"cmd": "enqueue", "payload": {"url": "https://a.com", "mode": "video", "options": {"height": "1080"}}},
    {"cmd": "enqueue", "payload": {"url": "https://a.com", "mode": "audio", "options": {"mp3_bitrate": 999}}},
    {"cmd": "enqueue", "payload": {"url": "https://a.com", "mode": "video", "options": {"cookies": "x"}}},
    {"cmd": "cancel", "payload": {"id": "../../etc"}},
    {"cmd": "set_settings", "payload": {"settings": {"max_concurrent": 50}}},
    {"cmd": "set_settings", "payload": {"settings": {"shell": "rm -rf"}}},
    {"cmd": "enqueue_batch", "payload": {"entries": [{"url": "https://a.com"}] * 201, "mode": "video"}},
])
def test_rejeita_mensagens_invalidas(msg):
    with pytest.raises(ProtocolError):
        validate_request(msg)


def test_aceita_mensagem_valida():
    mid, cmd, p = validate_request({"id": "m-1", "cmd": "enqueue", "payload": {"url": "https://a.com/x", "mode": "video", "options": {"height": 720, "container": "mp4"}, "meta": {"title": "t"}}})
    assert (mid, cmd, p["options"]["height"]) == ("m-1", "enqueue", 720)
