# Código-fonte correspondente

Este pacote contém o executável do aplicativo auxiliar, construído com PyInstaller a partir de:

| Componente | Versão | Licença | Onde obter o código-fonte |
|---|---|---|---|
| Baixaí (código próprio) | 0.2.0 | GPL-2.0-ou-posterior | arquivo `baixai-source-0.2.0.tar.gz` distribuído junto deste pacote |
| yt-dlp | 2026.10.26 | Unlicense | https://github.com/yt-dlp/yt-dlp (tag 2026.10.26) |
| gallery-dl | 1.32.18 | GPL-2.0-only | pasta `sources/` deste pacote; https://github.com/mikf/gallery-dl |
| mutagen | 1.48.1 | GPL-2.0-ou-posterior | pasta `sources/` deste pacote |
| certifi | 2026.10.23 | MPL-2.0 | pasta `sources/` deste pacote |
| PyInstaller | 6.22.3 | GPL-2.0-ou-posterior com exceção | https://github.com/pyinstaller/pyinstaller |
| Python | 3.12 | PSF-2.0 | https://www.python.org/downloads/ |

Demais bibliotecas (permissivas) e seus textos de licença estão em `THIRD_PARTY_NOTICES.md`.

## Reconstruir o executável

```sh
python3.12 -m venv .venv && .venv/bin/pip install -e helper pyinstaller
scripts/package-helper.sh        # gera dist/baixai-helper-<versão>-<so>-<arquitetura>.tar.gz
```

## FFmpeg

O FFmpeg **não** está neste pacote. Se você aceitar o download opcional do instalador (macOS arm64), ele obtém o build
de https://ffmpeg.martin-riedl.de (GPL-3.0-ou-posterior; fonte e script de build em https://git.martin-riedl.de/ffmpeg/build-script
e em https://ffmpeg.org/download.html). O instalador confere o SHA-256 antes de usar o arquivo.

Se precisar de qualquer código-fonte acima e não o encontrar, abra uma solicitação no repositório do projeto.
