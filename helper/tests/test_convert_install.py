import json
import sys

import pytest
from PIL import Image

from baixai_helper import install_host
from baixai_helper.convert import convert_image
from baixai_helper.errors import BaixaiError


def test_png_com_transparencia_para_jpeg_avisa_e_achata(tmp_path):
    src = tmp_path / "a.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 0)).save(src)  # totalmente transparente
    out, notes = convert_image(src, "jpeg")
    assert out.suffix == ".jpg" and not src.exists()
    assert any("transparência" in n for n in notes)
    with Image.open(out) as im:
        assert im.getpixel((1, 1))[0] > 240 and im.getpixel((1, 1))[2] > 240  # fundo branco


def test_jpeg_para_png_e_mesmo_formato_nao_converte(tmp_path):
    src = tmp_path / "a.jpg"
    Image.new("RGB", (4, 4), (10, 20, 30)).save(src)
    out, _ = convert_image(src, "png")
    assert out.suffix == ".png" and out.exists() and not src.exists()
    same, notes = convert_image(out, "png")
    assert same == out and notes == []
    assert convert_image(out, "original")[0] == out


def test_conversao_invalida_mantem_original(tmp_path):
    src = tmp_path / "quebrada.webp"
    src.write_bytes(b"nao e imagem")
    out, notes = convert_image(src, "jpeg")
    assert out == src and src.exists() and notes and not (tmp_path / "quebrada.jpg").exists()


def test_instala_e_remove_manifesto(tmp_path, monkeypatch):
    monkeypatch.setattr(install_host.Path, "home", classmethod(lambda cls: tmp_path))
    exe = tmp_path / "host"; exe.write_text("#!/bin/sh\n"); exe.chmod(0o755)
    ext = "a" * 32
    written = install_host.install(str(exe), [ext, "b" * 32], ["chrome", "chromium"])
    assert len(written) == 2
    m = json.loads(open(written[0]).read())
    assert m["name"] == "local.baixai.helper" and m["type"] == "stdio" and m["path"] == str(exe)
    assert m["allowed_origins"] == [f"chrome-extension://{ext}/", f"chrome-extension://{'b' * 32}/"]
    assert all(s["valid"] and s["path_exists"] for s in install_host.status())
    removed = install_host.uninstall(["chrome", "chromium"])
    # No Windows há um único arquivo de manifesto, compartilhado pelos navegadores via registro; nos demais, um por navegador.
    assert len(removed) == (1 if sys.platform == "win32" else 2) and install_host.status() == []


@pytest.mark.parametrize("bad", ["", "abc", "A" * 32, "q" * 32, "a" * 31, "chrome-extension://" + "a" * 32])
def test_id_invalido(tmp_path, bad):
    exe = tmp_path / "h"; exe.write_text("x"); exe.chmod(0o755)
    with pytest.raises(BaixaiError):
        install_host.install(str(exe), [bad], ["chrome"])


def test_executavel_precisa_ser_absoluto_e_existir(tmp_path):
    with pytest.raises(BaixaiError):
        install_host.install("host", ["a" * 32], ["chrome"])
    with pytest.raises(BaixaiError):
        install_host.install(str(tmp_path / "nao-existe"), ["a" * 32], ["chrome"])
