## Baixaí v0.1.1 — pré-lançamento

> **Esta versão substitui a v0.1.0**, cujo instalador não conseguia baixar o FFmpeg e o Deno (e links diretos por HTTPS) em computadores de usuários: faltava o pacote de certificados TLS dentro do executável. Se você instalou a v0.1.0, rode o comando de instalação de novo.

Baixe vídeos, áudios e imagens de um link, direto do **terminal**, no seu computador. Sem servidor, sem conta, sem telemetria.

### Instalar (cole no terminal)

**macOS e Linux**:
```sh
curl -fsSL https://raw.githubusercontent.com/Forbahl10/baixai/main/get.sh | sh
```
**Windows 10/11** (PowerShell):
```powershell
irm https://raw.githubusercontent.com/Forbahl10/baixai/main/get.ps1 | iex
```
O instalador confere o SHA-256, instala só para o seu usuário (sem `sudo`/administrador) e **pergunta** antes de mexer no PATH e antes de baixar o FFmpeg e o Deno. Depois, abra um **novo terminal** e use, **sempre com o link entre aspas**:

```sh
baixai "LINK"          # vídeo em MP4 (até 1080p)
baixai -a "LINK"       # só o áudio, em MP3
baixai -i "LINK"       # imagens
baixai --help
```

### Arquivos desta Release

| Arquivo | Para quê |
|---|---|
| `baixai-helper-0.1.1-macos-arm64.tar.gz` | macOS Apple Silicon (M1 ou mais novo) |
| `baixai-helper-0.1.1-macos-x86_64.tar.gz` | macOS Intel |
| `baixai-helper-0.1.1-windows-x86_64.zip` | Windows 10/11 |
| `baixai-helper-0.1.1-linux-x86_64.tar.gz` | Linux x86_64 |
| `baixai-extension-0.1.1*.zip` | Extensão do Chrome (opcional, experimental, não testada em Chrome real) |
| `baixai-source-0.1.1.tar.gz` | Código-fonte |
| `SHA256SUMS.txt` | Checksums de todos os arquivos |

Você também pode baixar o pacote do seu sistema, extrair e rodar `./install.sh` (macOS/Linux) ou `instalar.bat` (Windows).

### Leia antes de usar

- **Pré-lançamento.** O aplicativo **não é assinado** pela Apple nem pela Microsoft; o sistema pode mostrar um alerta.
- **Testado com links reais**: YouTube (vídeo e áudio) e imagem do X, em macOS Apple Silicon. Instalação, FFmpeg, Deno e conversões são exercitados pela integração contínua do repositório; veja `docs/MATRIZ.md` para o que foi e o que não foi verificado em cada sistema. Instagram, TikTok, SoundCloud e playlists estão implementados, **mas não validados ao vivo**.
- Só **conteúdo público**: sem login, cookies, DRM ou paywall. Muito conteúdo do Instagram, TikTok e X exige login e não funciona.
- Baixe apenas conteúdo **próprio, autorizado ou permitido**. Projeto independente, sem parceria com nenhuma plataforma.

### Licenças
**GPL-2.0-ou-posterior**. FFmpeg (GPL-3.0) e Deno (MIT) não vão no pacote: são baixados na instalação, com a sua confirmação. Avisos de terceiros em `THIRD_PARTY_NOTICES.md` e fontes em `baixai-source-0.1.1.tar.gz`.
