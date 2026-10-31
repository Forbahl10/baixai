# Avisos de terceiros

Gerado por `scripts/gen_inventory.py`. O Baixaí (código próprio) é distribuído sob **GPL-2.0-ou-posterior** (ver `LICENSE`).
O pacote do aplicativo auxiliar embute o **gallery-dl (GPL-2.0-only)** no mesmo executável, portanto a distribuição combinada segue a GPL-2.0.
Isso não é consultoria jurídica: revise antes de publicar.

A extensão do Chrome **não** contém código de terceiros além das APIs do navegador (o bundle é só código próprio compilado de TypeScript).

## Resumo

| Componente | Versão | Licença | Incluído em |
|---|---|---|---|
| yt-dlp | 2026.10.26 | Unlicense | executável do helper (PyInstaller) |
| yt-dlp-ejs | 0.8.0 | Unlicense AND MIT AND ISC | executável do helper (PyInstaller) |
| gallery_dl | 1.32.18 | GPL-2.0-only | executável do helper (PyInstaller) |
| pillow | 13.0.0 | MIT-CMU | executável do helper (PyInstaller) |
| requests | 2.34.2 | Apache-2.0 | executável do helper (PyInstaller) |
| urllib3 | 2.8.0 | MIT | executável do helper (PyInstaller) |
| certifi | 2026.10.23 | MPL-2.0 | executável do helper (PyInstaller) |
| idna | 3.20 | BSD-3-Clause | executável do helper (PyInstaller) |
| charset-normalizer | 3.5.2 | MIT | executável do helper (PyInstaller) |
| brotli | 1.2.1 | MIT | executável do helper (PyInstaller) |
| mutagen | 1.48.1 | GPL-2.0-or-later | executável do helper (PyInstaller) |
| pycryptodomex | 3.24.1 | BSD, Public Domain | executável do helper (PyInstaller) |
| websockets | 17.4 | BSD-3-Clause | executável do helper (PyInstaller) |
| Python (runtime CPython) | 3.12 | PSF-2.0 | executável do helper |
| PyInstaller (bootloader) | 6.22.3 | GPL-2.0-or-later com exceção para o programa empacotado | executável do helper |
| FFmpeg | 9.0.2 (build testado: martin-riedl.de macOS arm64) | GPL-3.0-or-later (build com --enable-gpl --enable-version3) | NÃO incluído nos pacotes. O instalador só o baixa se o usuário aceitar; o build testado é GPLv3 e inclui x264/x265/LAME. |
| Deno / Node.js (runtime JS opcional p/ YouTube) | - | MIT | NÃO incluído; detectado se instalado pelo usuário |

## Código-fonte correspondente

Para os componentes copyleft (GPL/LGPL/MPL) o código-fonte das versões distribuídas está na pasta `sources/` do pacote do aplicativo auxiliar
e nos endereços abaixo. Para FFmpeg (se você optar por baixá-lo), veja a página do build usado.

- gallery_dl 1.32.18: `gallery_dl-1.32.18.tar.gz` (sha256 `1c5562af3799a0bec96be0f64d95a416aee688fd09fe3893ca3a6c87bbe65bcd`) — https://files.pythonhosted.org/packages/ec/55/e40b8ce403489e7b3122eee28693efd885ca68256a9c6344fdfbd0842c3e/gallery_dl-1.32.18.tar.gz
- certifi 2026.10.23: `certifi-2026.10.23.tar.gz` (sha256 `a9895e6e2758b371e0545e321a3a8fd1fcfd9829ada8824a936dfb16aaaf36cd`) — https://files.pythonhosted.org/packages/fd/11/b524cbd9bbdaca58608e4cf4053fd463417549e1959fa8d3aa18319f9555/certifi-2026.10.23.tar.gz
- mutagen 1.48.1: `mutagen-1.48.1.tar.gz` (sha256 `8f95637ab9f6f305cec6bd1294e197debe207998e3e068596563c74f86b0a173`) — https://files.pythonhosted.org/packages/df/70/1675da133ea92227da41bf5b24e1c66be597ff736a1533ade41da986852f/mutagen-1.48.1.tar.gz

## Textos das licenças

### yt-dlp 2026.10.26 — Unlicense

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### yt-dlp-ejs 0.8.0 — Unlicense AND MIT AND ISC

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### gallery_dl 1.32.18 — GPL-2.0-only

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### pillow 13.0.0 — MIT-CMU

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### requests 2.34.2 — Apache-2.0

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### urllib3 2.8.0 — MIT

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### certifi 2026.10.23 — MPL-2.0

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### idna 3.20 — BSD-3-Clause

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### charset-normalizer 3.5.2 — MIT

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### brotli 1.2.1 — MIT

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### mutagen 1.48.1 — GPL-2.0-or-later

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### pycryptodomex 3.24.1 — BSD, Public Domain

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

### websockets 17.4 — BSD-3-Clause

(arquivo de licença não encontrado nos metadados do pacote; consulte a página do projeto)

