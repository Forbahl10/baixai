import threading
import time

import pytest

from baixai_helper.errors import BaixaiError
from baixai_helper.queue import JobQueue
from baixai_helper.settings import Settings
from baixai_helper.store import Store
from baixai_helper.tools import Tools

from conftest import FakeEngine, wait_for

URL = "https://www.youtube.com/watch?v=aaaaaaaaaaa"


def make(tmp_path, eng, **settings):
    store = Store(tmp_path / "q.db")
    st = Settings(store)
    st.update({"download_dir": str(tmp_path / "dl"), **settings})
    events = []
    q = JobQueue(store, st, Tools(st), emit=events.append, engines={"ytdlp": eng, "gallerydl": eng, "direct": eng})
    return q, store, events


def state(q, jid):
    return next(j["state"] for j in q.list() if j["id"] == jid)


def test_fluxo_completo_e_arquivo_nao_sobrescreve(tmp_path, offline):
    q, store, events = make(tmp_path, FakeEngine("ok"))
    q.start()
    a = q.enqueue(URL, "video", {"height": 720}, {"title": "T", "author": "Autor"}, force=True)["job"]
    wait_for(lambda: state(q, a["id"]) == "done")
    b = q.enqueue(URL, "video", {"height": 720}, force=True)["job"]
    wait_for(lambda: state(q, b["id"]) == "done")
    files = [f["path"] for j in q.list() for f in j["files"]]
    assert len(set(files)) == 2 and all((tmp_path / "dl" / "YouTube") in __import__("pathlib").Path(f).parents for f in files)
    assert not (tmp_path / "dl" / ".baixai-tmp").exists()
    seen = [e["job"]["state"] for e in events if e.get("event") == "job" and e["job"]["id"] == a["id"]]
    assert seen[0] == "waiting" and "analyzing" in seen and "downloading" in seen and seen[-1] == "done"
    q.shutdown()


def test_organizar_por_autor(tmp_path, offline):
    q, *_ = make(tmp_path, FakeEngine("ok"), organize_by_author=True)
    q.start()
    j = q.enqueue(URL, "video", {}, {"author": "../../Mal/Autor"})["job"]
    wait_for(lambda: state(q, j["id"]) == "done")
    p = __import__("pathlib").Path(q.list()[0]["files"][0]["path"])
    assert (tmp_path / "dl").resolve() in p.resolve().parents and ".." not in p.parts
    q.shutdown()


def test_falha_e_repeticao(tmp_path, offline):
    eng = FakeEngine("fail")
    q, *_ = make(tmp_path, eng)
    q.start()
    j = q.enqueue(URL, "audio")["job"]
    wait_for(lambda: state(q, j["id"]) == "failed")
    job = q.list()[0]
    assert job["error"]["code"] == "network" and job["error"]["message"] and job["attempts"] == 1
    eng.behavior = "ok"
    q.retry(j["id"])
    wait_for(lambda: state(q, j["id"]) == "done")
    assert q.list()[0]["attempts"] == 2 and q.list()[0]["error"] is None
    q.shutdown()


def test_excecao_inesperada_nao_derruba_a_fila(tmp_path, offline):
    q, *_ = make(tmp_path, FakeEngine("crash"))
    q.start()
    j = q.enqueue(URL, "audio")["job"]
    wait_for(lambda: state(q, j["id"]) == "failed")
    assert "boom" not in (q.list()[0]["error"]["message"])
    q.shutdown()


def test_cancelar_em_andamento_e_aguardando(tmp_path, offline):
    eng = FakeEngine("slow")
    q, *_ = make(tmp_path, eng, max_concurrent=1)
    q.start()
    a = q.enqueue(URL, "video")["job"]
    b = q.enqueue("https://www.youtube.com/watch?v=bbbbbbbbbbb", "video")["job"]
    wait_for(lambda: state(q, a["id"]) == "downloading")
    assert state(q, b["id"]) == "waiting"
    q.cancel(b["id"])
    assert state(q, b["id"]) == "cancelled"
    q.cancel(a["id"])
    wait_for(lambda: state(q, a["id"]) == "cancelled")
    assert not (tmp_path / "dl" / ".baixai-tmp" / a["id"]).exists()
    q.retry(b["id"])  # cancelado pode ser repetido
    eng.behavior = "ok"
    wait_for(lambda: state(q, b["id"]) == "done")
    q.shutdown()


def test_limite_de_concorrencia(tmp_path, offline):
    eng = FakeEngine("gate")
    q, *_ = make(tmp_path, eng, max_concurrent=2)
    q.start()
    ids = [q.enqueue(f"https://www.youtube.com/watch?v={c * 11}", "video")["job"]["id"] for c in "abcde"]
    wait_for(lambda: eng.max_running == 2)
    time.sleep(0.3)
    assert eng.max_running == 2 and sum(state(q, i) in ("downloading", "analyzing") for i in ids) == 2
    eng.release.set()
    wait_for(lambda: all(state(q, i) == "done" for i in ids))
    assert eng.max_running == 2
    q.shutdown()


def test_duplicacao_acidental(tmp_path, offline):
    eng = FakeEngine("gate")
    q, *_ = make(tmp_path, eng)
    q.start()
    first = q.enqueue(URL + "#trecho", "video", {"height": 720})
    again = q.enqueue(URL, "video", {"height": 720})
    assert first["duplicate"] is None and again["duplicate"] == "active" and again["job"]["id"] == first["job"]["id"]
    assert q.enqueue(URL, "video", {"height": 480})["duplicate"] is None  # opções diferentes = outro trabalho
    eng.release.set()
    wait_for(lambda: state(q, first["job"]["id"]) == "done")
    assert q.enqueue(URL, "video", {"height": 720})["duplicate"] == "done"
    assert q.enqueue(URL, "video", {"height": 720}, force=True)["duplicate"] is None
    q.shutdown()


def test_recuperacao_apos_reinicio(tmp_path, offline):
    eng = FakeEngine("gate")
    q, store, _ = make(tmp_path, eng)
    q.start()
    a = q.enqueue(URL, "video")["job"]
    b = q.enqueue("https://www.youtube.com/watch?v=bbbbbbbbbbb", "audio")["job"]
    wait_for(lambda: state(q, a["id"]) == "downloading")
    q.shutdown()  # encerramento do host: trabalho interrompido volta a "aguardando", não "cancelado"
    assert state(q, a["id"]) == "waiting"
    store.close()

    # simula morte abrupta: estado "downloading" gravado no banco
    store2 = Store(tmp_path / "q.db")
    store2.update(a["id"], state="downloading")
    st2 = Settings(store2)
    eng2 = FakeEngine("ok")
    q2 = JobQueue(store2, st2, Tools(st2), engines={"ytdlp": eng2, "gallerydl": eng2, "direct": eng2})
    q2.start()
    wait_for(lambda: {j["state"] for j in q2.list()} == {"done"})
    assert {j["id"] for j in q2.list()} == {a["id"], b["id"]}
    q2.shutdown()


def test_remover_e_limpar_historico(tmp_path, offline):
    q, *_ = make(tmp_path, FakeEngine("ok"))
    q.start()
    ids = [q.enqueue(f"https://www.youtube.com/watch?v={c * 11}", "video")["job"]["id"] for c in "ab"]
    wait_for(lambda: all(state(q, i) == "done" for i in ids))
    files = [f["path"] for j in q.list() for f in j["files"]]
    q.remove(ids[0])
    assert len(q.list()) == 1
    assert q.clear_history() == 1 and q.list() == []
    assert all(__import__("pathlib").Path(f).exists() for f in files)  # arquivos baixados nunca são apagados
    q.shutdown()


def test_validacoes_de_enfileiramento(tmp_path, offline):
    q, *_ = make(tmp_path, FakeEngine("ok"))
    for bad, mode in [("ftp://x.com/a", "video"), ("https://www.youtube.com/watch?v=abc", "image"), ("https://www.instagram.com/someuser/", "image")]:
        with pytest.raises(BaixaiError):
            q.enqueue(bad, mode)
    with pytest.raises(BaixaiError):
        q.retry("inexistente")


def test_log_por_trabalho_e_redacao(tmp_path, offline):
    class Chatty(FakeEngine):
        def download(self, spec, outdir, ctx):
            ctx.log("baixando https://x.com/a?token=SEGREDO Cookie: sessionid=ZZZ")
            return super().download(spec, outdir, ctx)
    q, *_ = make(tmp_path, Chatty("ok"))
    q.start()
    j = q.enqueue(URL, "video")["job"]
    wait_for(lambda: state(q, j["id"]) == "done")
    logs = "\n".join(q.logs(j["id"]))
    assert "SEGREDO" not in logs and "ZZZ" not in logs and "baixando" in logs
    q.shutdown()
