# Baixaí

Baixe **vídeos, áudios e imagens** de um link, direto do **terminal**. Tudo roda no seu computador: nenhum servidor processa seus downloads, não há conta e não há telemetria.

```sh
baixai "https://www.youtube.com/watch?v=..."      # vídeo em MP4 (até 1080p)
baixai -a "LINK"                                   # só o áudio, em MP3
baixai -i "LINK"                                   # imagens de um post ou galeria
baixai -q 720 -o ~/Videos "LINK"                   # no máximo 720p, numa pasta à escolha
```

Usa o [yt-dlp](https://github.com/yt-dlp/yt-dlp) (vídeo e áudio), o [gallery-dl](https://github.com/mikf/gallery-dl) (imagens e galerias) e o FFmpeg (converter e juntar faixas), isolados por adaptadores. Fila persistente em SQLite, progresso na tela, cancelamento com Ctrl+C e arquivos sem sobrescrever os existentes.

> Projeto independente, sem parceria com YouTube, Instagram, TikTok, X, SoundCloud ou qualquer plataforma. Baixe apenas conteúdo **próprio, autorizado ou permitido** pelo autor, pela licença e pelos termos da plataforma. Não contorna DRM, paywalls nem controles de acesso e não usa login nem cookies.

## Instalar (cole no terminal)

**macOS e Linux**:

```sh
curl -fsSL https://raw.githubusercontent.com/Forbahl10/baixai/main/get.sh | sh
```

**Windows 10/11** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/Forbahl10/baixai/main/get.ps1 | iex
```

O comando baixa o pacote da [última Release](https://github.com/Forbahl10/baixai/releases/latest), **confere o SHA-256** e instala só para o seu usuário (sem `sudo` nem administrador). Durante a instalação ele **pergunta** antes de:

1. acrescentar o comando `baixai` ao PATH do seu usuário (uma linha no `~/.zshrc`/`~/.bashrc`, ou no PATH do usuário no Windows);
2. baixar o **FFmpeg** (MP3 e vídeo em alta qualidade) e o **Deno** (necessário para o YouTube), com SHA-256 fixado no código, guardados só na pasta do Baixaí.

Depois, **abra um novo terminal** e use `baixai "LINK"`. **Coloque sempre o link entre aspas**: sem elas, o `&` e o `?` dos links quebram o comando no terminal.

Prefere ler o script antes de rodar? [`get.sh`](get.sh) e [`get.ps1`](get.ps1) são curtos. Para remover tudo: `~/Library/Application\ Support/Baixai/desinstalar.sh` (macOS), `~/.local/share/baixai/desinstalar.sh` (Linux) ou `desinstalar.ps1` em `%APPDATA%\Baixai` (Windows). Seus arquivos baixados nunca são apagados.

### Comandos

| Comando | O que faz |
|---|---|
| `baixai "LINK"` | Baixa o vídeo em MP4 (até 1080p). Se o link só tem áudio ou imagem, baixa isso. |
| `baixai -a "LINK"` / `--bitrate 320` | Áudio em MP3 (192 kbps por padrão). |
| `baixai -i "LINK"` / `--formato-imagem png\|jpeg` | Imagens; converte se pedir (JPEG não tem transparência: o fundo vira branco, com aviso). |
| `-q ALTURA`, `-o PASTA`, `--original` | Altura máxima, pasta de destino e manter o formato original. |
| `--tudo`, `--itens 1,3,5` | Em listas e galerias grandes. Sem isso, o Baixaí pergunta antes de baixar tudo. |
| `baixai doctor` | Diagnóstico (versões, FFmpeg, Deno). |
| `baixai tools install-deps` | Instala/reinstala FFmpeg e Deno. |
| `baixai tools check` / `update-ytdlp` | Mostra versões e atualiza o yt-dlp **só quando você pede**. |

Os arquivos vão para `Downloads/Baixai/<plataforma>/`.

## O que funciona

Mostramos só o que foi realmente verificado. A tabela completa (plataforma × tipo de conteúdo × sistema) está em [`docs/MATRIZ.md`](docs/MATRIZ.md) e os testes em [`docs/TESTES.md`](docs/TESTES.md).

- **Testado com links reais**: YouTube (vídeo MP4 e áudio MP3) e imagem de post público do X, em macOS (Apple Silicon).
- **Implementado, ainda não validado ao vivo**: Instagram, TikTok, SoundCloud, vídeo do X e playlists. Muito conteúdo dessas plataformas exige login, que **não é suportado**.
- Só **conteúdo público**.

## Extensão do Chrome (opcional, experimental)

O repositório também inclui uma extensão do Chrome (Manifest V3) que usa o mesmo aplicativo por Native Messaging. **Ela ainda não foi testada num Chrome real e não está na Chrome Web Store.** O Chrome não permite instalar extensões por linha de comando: é preciso `chrome://extensions` → Modo do desenvolvedor → Carregar sem compactação. Detalhes em [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) e `docs/chrome-web-store/`. Para registrar o host dela: `./install.sh --with-extension` (ID de desenvolvimento em `extension/dev-extension-id.txt`).

## Desenvolvimento

Requisitos: Python ≥ 3.11 e, para a extensão, Node.js ≥ 22.

```sh
python3.12 -m venv .venv && .venv/bin/pip install -e "helper[dev]"
.venv/bin/python -m pytest helper/tests -q                # testes determinísticos, sem rede
.venv/bin/python -m baixai_helper "LINK"                   # o mesmo que `baixai`
.venv/bin/python scripts/package_helper.py --source        # empacota para o seu sistema (PyInstaller)
.venv/bin/python scripts/smoke_package.py dist             # instala o pacote como o usuário e baixa de verdade
```

A CI (`.github/workflows/build.yml`) roda os testes e o teste de fumaça do pacote em macOS (Apple Silicon e Intel), Windows e Linux, e publica a Release quando uma tag `v*` é enviada.

## Segurança e privacidade

Sem shell (argumentos estruturados), validação de links com proteção contra SSRF e redirecionamentos para a rede local, nomes de arquivo sanitizados, nada gravado fora das pastas do Baixaí e dos downloads, sem telemetria. Nada é baixado ou atualizado sem ação sua: FFmpeg e Deno só quando você aceita, e o yt-dlp só em `baixai tools update-ytdlp`. Veja [`docs/PRIVACIDADE.md`](docs/PRIVACIDADE.md).

## Licenças

Código do Baixaí: **GPL-2.0-ou-posterior** ([`LICENSE`](LICENSE)). O pacote embute o gallery-dl (GPL-2.0-only) no mesmo executável. FFmpeg (build GPL-3.0) e Deno (MIT) **não** vão dentro do pacote: são baixados na instalação, com a sua confirmação. Há [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), inventário em `dist/inventory.json`, oferta de código-fonte (`packaging/CODIGO-FONTE.md`) e os fontes dos componentes copyleft em `sources/`. Isto não é consultoria jurídica: revise antes de redistribuir.
