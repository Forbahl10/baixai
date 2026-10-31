# Baixaí

Extensão do Chrome (Manifest V3) + aplicativo auxiliar local para baixar **vídeos, áudios, imagens e galerias** a partir de um link. Tudo roda no seu computador: nenhum servidor público processa downloads, não há conta e não há telemetria.

- **Facilidade de colar um link**: campo em destaque → *Analisar* → prévia → formato/qualidade → *Adicionar à fila*.
- **Capacidade de download do [yt-dlp](https://github.com/yt-dlp/yt-dlp)** (vídeo/áudio) e **imagens/galerias do [gallery-dl](https://github.com/mikf/gallery-dl)**, isolados por adaptadores; FFmpeg para converter e combinar faixas.
- Comunicação por **Chrome Native Messaging** (sem portas abertas).
- Interface em pt-BR, tema claro/escuro, navegação por teclado.

> Projeto independente, sem parceria com YouTube, Instagram, TikTok, X, SoundCloud ou qualquer plataforma. Baixe apenas conteúdo **próprio, autorizado ou permitido**. Não contorna DRM, paywalls nem controles de acesso e não usa login/cookies. O cobalt foi usado apenas como referência de experiência de uso: nenhum código, marca ou identidade visual dele foi copiado.

**Estado: MVP (v0.1.0).** O que foi realmente testado e o que não foi está em [`docs/MATRIZ.md`](docs/MATRIZ.md) e [`docs/TESTES.md`](docs/TESTES.md). **Nada foi publicado** (loja, site ou releases): veja [`docs/chrome-web-store/checklist.md`](docs/chrome-web-store/checklist.md).

## Instalação rápida (cole no terminal)

**macOS (Apple Silicon ou Intel) e Linux** — cole no Terminal:

```sh
curl -fsSL https://raw.githubusercontent.com/Forbahl10/baixai/main/get.sh | sh
```

**Windows 10/11** — cole no PowerShell:

```powershell
irm https://raw.githubusercontent.com/Forbahl10/baixai/main/get.ps1 | iex
```

O comando baixa o pacote da [última Release](https://github.com/Forbahl10/baixai/releases/latest), confere o SHA-256, instala o aplicativo auxiliar **só para o seu usuário** (sem `sudo`/administrador) e deixa a extensão pronta em `~/Baixai/extensao` (Windows: `%USERPROFILE%\Baixai\extensao`). Ele só pergunta antes de baixar o FFmpeg.

**Falta 1 passo manual, e nenhum programa consegue fazê-lo por você** (o Chrome não permite instalar extensão por linha de comando): abra `chrome://extensions` → ative o **Modo do desenvolvedor** → **Carregar sem compactação** → escolha a pasta `Baixai/extensao`. Depois reinicie o Chrome e abra o Baixaí: deve aparecer **“Aplicativo local conectado”**. Não apague nem mova essa pasta.

Prefere ler o script antes de rodar? [`get.sh`](get.sh) e [`get.ps1`](get.ps1) têm poucas linhas. Para remover: `~/Baixai/desinstalar.sh` (Windows: `desinstalar.ps1` na mesma pasta).

## Instalação manual (usuário)

1. **Extensão**: extraia `dist/baixai-extension-0.1.0.zip` (ou use `dist/extension-unpacked/`), abra `chrome://extensions`, ative o *Modo do desenvolvedor* → *Carregar sem compactação*. Para a pasta `extension-unpacked` o ID é fixo: veja `dist/extension-dev-id.txt` (`gipfhgbdolmibhecjiemjdodedbfmahg`). Ao carregar o ZIP extraído, o ID será outro (copie-o de `chrome://extensions`).
2. **Aplicativo auxiliar** (macOS Apple Silicon testado):
   ```sh
   tar -xzf dist/baixai-helper-0.1.0-macos-arm64.tar.gz && cd baixai-helper-0.1.0-macos-arm64
   ./install.sh                         # extensão carregada de dist/extension-unpacked (ID padrão)
   ./install.sh --extension-id <ID>     # qualquer outro ID (repita para dev e produção)
   ```
   O instalador copia o app para a sua pasta de usuário, registra o host Native Messaging e **pergunta** antes de baixar o FFmpeg (verifica SHA-256). Sem `sudo`.
3. Reinicie o Chrome → o indicador deve mostrar **“Aplicativo local conectado”**. Se não: aba *Diagnóstico* ou `…/baixai-helper doctor`.

Remover: `./uninstall.sh` (`--purge-data` apaga fila/histórico/logs). Windows e Linux: scripts e instruções existem (`install.ps1`, `install.sh`), mas **não foram testados**.

### IDs da extensão (desenvolvimento × produção)

O host só aceita IDs listados em `allowed_origins`. **Desenvolvimento**: `extension/dev-public-key.txt` fixa o ID de `dist/extension-unpacked` (só a chave pública é guardada). **Produção**: o ID é atribuído pela Chrome Web Store; rode o instalador com `--extension-id <ID de produção>` (e, se quiser, também o de desenvolvimento). O ZIP da loja é gerado **sem** o campo `key`.

## Desenvolvimento

Requisitos: Python ≥ 3.11 (o yt-dlp não suporta 3.9/3.10 nas versões atuais), Node.js ≥ 22, FFmpeg no `PATH` (ou `BAIXAI_FFMPEG`), Deno ou Node 22+ para o YouTube.

```sh
python3.12 -m venv .venv && .venv/bin/pip install -e "helper[dev]"
npm install
scripts/make-all.sh          # testa e gera dist/ (extensão, helper, site, checksums)
```

Comandos úteis (fora do Chrome): `python -m baixai_helper analyze <url>`, `… download <url> --mode video --height 720`, `… doctor`, `… tools check|update-ytdlp`, `… install-host --extension-id <ID>`.

Estrutura e decisões: [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md). Privacidade: [`docs/PRIVACIDADE.md`](docs/PRIVACIDADE.md).

## Licenças

Código do Baixaí: **GPL-2.0-ou-posterior** (`LICENSE`). O pacote do aplicativo embute o gallery-dl (GPL-2.0-only) no mesmo executável; o FFmpeg (opcional) não é distribuído nos pacotes e o build testado é GPL-3.0. Executar uma dependência como subprocesso **não** foi tratado como eliminando obrigações: por isso há `THIRD_PARTY_NOTICES.md`, `dist/inventory.json`, oferta de código-fonte (`packaging/CODIGO-FONTE.md`) e os fontes dos componentes copyleft em `sources/`. Isto não é consultoria jurídica — revise antes de distribuir.
