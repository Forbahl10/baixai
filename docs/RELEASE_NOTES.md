## Baixaí v0.1.0 — pré-lançamento

Extensão do Chrome + aplicativo auxiliar que roda no **seu computador** para baixar vídeos, áudios e imagens a partir de um link. Sem servidor, sem conta, sem telemetria.

### Como instalar (3 passos)

**1. Extensão** — baixe `baixai-extension-0.1.0-manual.zip`, extraia em uma pasta que você vai manter, abra `chrome://extensions`, ative o **Modo do desenvolvedor** e clique em **Carregar sem compactação**. (O ID desta extensão é sempre `gipfhgbdolmibhecjiemjdodedbfmahg`.)

**2. Aplicativo auxiliar** — baixe o arquivo do seu sistema abaixo e extraia:

| Sistema | Arquivo | Instalar |
|---|---|---|
| **macOS (Apple Silicon, M1+)** | `baixai-helper-0.1.0-macos-arm64.tar.gz` | no Terminal, dentro da pasta extraída: `./install.sh` |
| macOS (Intel) | `baixai-helper-0.1.0-macos-x86_64.tar.gz` | `./install.sh` |
| **Windows 10/11** | `baixai-helper-0.1.0-windows-x86_64.zip` | dois cliques em **`instalar.bat`** |
| Linux (x86_64) | `baixai-helper-0.1.0-linux-x86_64.tar.gz` | `./install.sh` |

**3. Reinicie o Chrome** e abra o Baixaí: deve aparecer **“Aplicativo local conectado”**. Se não, abra a aba **Diagnóstico**.

O instalador **pergunta** antes de baixar o FFmpeg (necessário para MP3 e para juntar vídeo e áudio). Para remover: `./uninstall.sh` (macOS/Linux) ou `remover.bat` (Windows).

### Leia antes de usar

- **Pré-lançamento.** O aplicativo **não é assinado** pela Apple nem pela Microsoft: o macOS ou o Windows podem exibir alertas. O instalador cuida da marca de quarentena quando você o executa. A extensão ainda **não está na Chrome Web Store**.
- **Testado**: YouTube (vídeo MP4 e áudio MP3) e imagens do X em macOS; instalação, comunicação com o Chrome (simulada) e download/conversão de imagem do pacote em macOS, Windows e Linux pela integração contínua deste repositório. **Não testado ainda**: a interface da extensão num Chrome de verdade em todos os sistemas, e Instagram, TikTok e SoundCloud ao vivo. Veja `docs/MATRIZ.md`.
- Só **conteúdo público**: sem login, cookies, DRM ou paywall. Muito conteúdo do Instagram/TikTok/X exige login e não funciona.
- Para o YouTube funcionar por completo, instale **Deno** ou **Node.js 22+**.
- Baixe apenas conteúdo **próprio, autorizado ou permitido**. Projeto independente, sem parceria com nenhuma plataforma.

### Verificação e licenças
`SHA256SUMS.txt` lista os checksums. Licença **GPL-2.0-ou-posterior**; avisos de terceiros em `THIRD_PARTY_NOTICES.md` (dentro de cada pacote), código-fonte em `baixai-source-0.1.0.tar.gz`.
