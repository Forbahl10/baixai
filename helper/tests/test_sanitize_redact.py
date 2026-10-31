import sys
from pathlib import Path

import pytest

from baixai_helper.errors import BaixaiError
from baixai_helper.redact import redact
from baixai_helper.sanitize import safe_join, sanitize_component, sanitize_filename, unique_path


@pytest.mark.parametrize("raw", ["../../etc/passwd", "..", "...", ".hidden", "a/b\\c", "con", "NUL.txt", "a:b*c?.mp4", "x" * 500, "", "\x00\x01evil", "  espaços  ", "fim.", "ação/ü"])
def test_componente_nunca_escapa(raw):
    out = sanitize_component(raw)
    assert out and "/" not in out and "\\" not in out and out not in (".", "..") and not out.startswith(".") and not out.endswith((" ", "."))
    assert len(out.encode()) <= 150


def test_reservados_windows():
    assert sanitize_component("con") != "con" and sanitize_component("COM1.txt").startswith("_")


def test_filename_preserva_extensao_curta():
    assert sanitize_filename("../../a?b.MP4") == "b.mp4" or sanitize_filename("../../a?b.MP4").endswith(".mp4")
    assert sanitize_filename("sem extensão") == "sem extensão"
    assert sanitize_filename("x" * 400 + ".jpg").endswith(".jpg") and len(sanitize_filename("x" * 400 + ".jpg").encode()) <= 180


def test_safe_join_dentro_da_base(tmp_path):
    p = safe_join(tmp_path, "YouTube", "../../fora")
    assert tmp_path.resolve() in p.parents


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks exigem privilégio no Windows")
def test_safe_join_com_symlink_para_fora(tmp_path):
    out = tmp_path / "fora"; out.mkdir()
    base = tmp_path / "base"; base.mkdir()
    (base / "link").symlink_to(out)
    with pytest.raises(BaixaiError):
        safe_join(base, "link")


def test_unique_path_nao_sobrescreve(tmp_path):
    f = tmp_path / "a.mp4"; f.write_text("1")
    (tmp_path / "a (1).mp4").write_text("2")
    assert unique_path(f).name == "a (2).mp4"


def test_redact_remove_query_tokens_e_home():
    t = f"GET https://x.com/a?token=SEGREDO&sig=abc Authorization: Bearer abcdefghijkl Cookie: sessionid=XYZ {Path.home()}/f.mp4"
    out = redact(t)
    assert "SEGREDO" not in out and "abcdefghijkl" not in out and "XYZ" not in out and str(Path.home()) not in out
    assert "https://x.com/a" in out
