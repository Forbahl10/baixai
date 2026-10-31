"""Gera o inventário de dependências e o arquivo de avisos de terceiros a partir do ambiente instalado.

Uso: python scripts/gen_inventory.py [--fetch-sources]
  --fetch-sources  baixa do PyPI os códigos-fonte (sdist) dos componentes copyleft (GPL/LGPL/MPL) para dist/sources/
Saídas: THIRD_PARTY_NOTICES.md, dist/inventory.json (e dist/sources/*)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLED = ["yt-dlp", "yt-dlp-ejs", "gallery-dl", "Pillow", "requests", "urllib3", "certifi", "idna", "charset-normalizer", "brotli", "mutagen",
           "pycryptodomex", "websockets"]
COPYLEFT = re.compile(r"GPL|LGPL|MPL|Mozilla Public", re.I)
STATIC = [
    {"name": "Python (runtime CPython)", "version": "3.12", "license": "PSF-2.0", "home": "https://www.python.org/", "bundled": "executável do helper", "note": "Licença PSF: https://docs.python.org/3/license.html"},
    {"name": "PyInstaller (bootloader)", "version": "6.22.3", "license": "GPL-2.0-or-later com exceção para o programa empacotado", "home": "https://pyinstaller.org/",
     "bundled": "executável do helper", "note": "A exceção do bootloader permite distribuir o aplicativo empacotado sob qualquer licença; o restante do pacote segue as licenças abaixo."},
    {"name": "FFmpeg", "version": "9.0.2 (build testado: martin-riedl.de macOS arm64)", "license": "GPL-3.0-or-later (build com --enable-gpl --enable-version3)", "home": "https://ffmpeg.org/",
     "bundled": "NÃO incluído nos pacotes. O instalador só o baixa se o usuário aceitar; o build testado é GPLv3 e inclui x264/x265/LAME.", "note": "Código-fonte: https://ffmpeg.org/download.html e https://git.martin-riedl.de/ffmpeg/build-script"},
    {"name": "Deno / Node.js (runtime JS opcional p/ YouTube)", "version": "-", "license": "MIT", "home": "https://deno.com/ · https://nodejs.org/", "bundled": "NÃO incluído; detectado se instalado pelo usuário", "note": ""},
]


def dist_info(name: str):
    d = metadata.distribution(name)
    md = d.metadata
    lic = md.get("License-Expression") or md.get("License") or ""
    if not lic or len(lic) > 80:
        cls = [c.split("::")[-1].strip() for c in md.get_all("Classifier") or [] if c.startswith("License ::")]
        lic = lic if lic and len(lic) <= 80 else "; ".join(cls) or "ver texto da licença"
    texts = []
    for f in d.files or []:
        if re.search(r"(^|/)(LICEN[SC]E|COPYING|NOTICE)[^/]*$", str(f), re.I) and f.suffix.lower() in ("", ".txt", ".md", ".rst"):
            try:
                texts.append((f.name, f.read_text(encoding="utf-8", errors="replace")))
            except Exception:
                pass
    url = md.get("Home-page") or next((u.split(",")[-1].strip() for u in md.get_all("Project-URL") or [] if "ource" in u or "ome" in u), "")
    return {"name": md["Name"], "version": md["Version"], "license": lic, "home": url, "texts": texts}


def fetch_source(name: str, version: str, out: Path) -> dict | None:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=60) as r:
        data = json.load(r)
    for u in data["urls"]:
        if u["packagetype"] == "sdist":
            dest = out / u["filename"]
            blob = urllib.request.urlopen(u["url"], timeout=120).read()
            if hashlib.sha256(blob).hexdigest() != u["digests"]["sha256"]:
                raise SystemExit(f"checksum divergente em {u['filename']}")
            dest.write_bytes(blob)
            return {"file": dest.name, "sha256": u["digests"]["sha256"], "url": u["url"]}
    return None


def main() -> None:
    fetch = "--fetch-sources" in sys.argv
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    comps = [dist_info(n) for n in BUNDLED]
    inventory = []
    for c in comps:
        entry = {k: c[k] for k in ("name", "version", "license", "home")}
        entry["bundled"] = "executável do helper (PyInstaller)"
        entry["copyleft"] = bool(COPYLEFT.search(c["license"]))
        if fetch and entry["copyleft"]:
            src = dist / "sources"; src.mkdir(exist_ok=True)
            entry["source"] = fetch_source(c["name"], c["version"], src)
        inventory.append(entry)
    inventory += [{**s, "copyleft": bool(COPYLEFT.search(s["license"]))} for s in STATIC]
    (dist / "inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n")

    lines = ["# Avisos de terceiros", "",
             "Gerado por `scripts/gen_inventory.py`. O Baixaí (código próprio) é distribuído sob **GPL-2.0-ou-posterior** (ver `LICENSE`).",
             "O pacote do aplicativo auxiliar embute o **gallery-dl (GPL-2.0-only)** no mesmo executável, portanto a distribuição combinada segue a GPL-2.0.",
             "Isso não é consultoria jurídica: revise antes de publicar.", "",
             "A extensão do Chrome **não** contém código de terceiros além das APIs do navegador (o bundle é só código próprio compilado de TypeScript).", "",
             "## Resumo", "", "| Componente | Versão | Licença | Incluído em |", "|---|---|---|---|"]
    for e in inventory:
        lines.append(f"| {e['name']} | {e['version']} | {e['license']} | {e['bundled']} |")
    lines += ["", "## Código-fonte correspondente", "",
              "Para os componentes copyleft (GPL/LGPL/MPL) o código-fonte das versões distribuídas está na pasta `sources/` do pacote do aplicativo auxiliar",
              "e nos endereços abaixo. Para FFmpeg (se você optar por baixá-lo), veja a página do build usado.", ""]
    for e in inventory:
        if e.get("source"):
            lines.append(f"- {e['name']} {e['version']}: `{e['source']['file']}` (sha256 `{e['source']['sha256']}`) — {e['source']['url']}")
    lines += ["", "## Textos das licenças", ""]
    for c in comps:
        lines += [f"### {c['name']} {c['version']} — {c['license']}", ""]
        for fname, text in c["texts"][:3]:
            lines += [f"<details><summary>{fname}</summary>", "", "```text", text.strip()[:12000], "```", "", "</details>", ""]
        if not c["texts"]:
            lines += ["(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)", ""]
    (ROOT / "THIRD_PARTY_NOTICES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(inventory)} componentes no inventário; THIRD_PARTY_NOTICES.md atualizado")


if __name__ == "__main__":
    main()
