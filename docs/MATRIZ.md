# Matriz de suporte (plataforma × tipo de conteúdo)

Atualizada em **30/10/2026**. Legenda:

- ✅ **Implementado e testado** — executado de verdade (rede + plataforma) nesta versão, com a data e o ambiente indicados.
- 🟡 **Implementado, não validado ao vivo** — o código existe e os testes com fixtures passam, mas nenhum download real foi feito.
- ❌ **Não suportado**
- ⚠️ **Limitação conhecida**

Estar listada em yt-dlp ou gallery-dl **não** é tratado como garantia. Plataformas mudam sem aviso; o app mostra só as opções que a análise do link realmente encontrou.

| Plataforma | Vídeo MP4 | Áudio MP3 | Imagens / galerias | Playlists / coleções |
|---|---|---|---|---|
| **YouTube** | ✅ vídeo público, MP4 H.264+AAC em 350p e 262p, combinando faixas (FFmpeg) | ✅ MP3 192 kbps com capa e metadados | ❌ (miniatura não é oferecida) | 🟡 análise e fila por item implementadas |
| **X (Twitter)** | 🟡 yt-dlp (o post de teste não tinha vídeo: o yt-dlp respondeu “No video could be found” e o app caiu para o gallery-dl, como projetado) | 🟡 | ✅ post público com 1 imagem: original e conversão para PNG | ❌ |
| **Instagram** | 🟡 reels via yt-dlp | 🟡 | 🟡 posts/carrosséis via gallery-dl | ❌ |
| **TikTok** | 🟡 yt-dlp | 🟡 | 🟡 fotos via gallery-dl | ❌ |
| **SoundCloud** | ❌ | 🟡 yt-dlp (MP3 é reconvertido da fonte) | ❌ | 🟡 sets |
| **Link direto** (imagem/áudio/vídeo por URL) | ⚠️ só formato original | ✅ áudio direto → MP3 (FFmpeg) | ✅ imagem direta, original/JPEG/PNG, com aviso de transparência | ❌ |

## Limitações conhecidas

- **Login e conteúdo privado**: o MVP baixa **somente conteúdo público**, sem cookies nem login. Instagram, TikTok e X frequentemente exigem login para parte do conteúdo; nesses casos o app mostra uma mensagem clara em vez de falhar em silêncio. Stories do Instagram não são suportados.
- **YouTube e runtime JavaScript**: o yt-dlp precisa de Deno ou Node.js 22+ para resolver os desafios do YouTube. Sem isso, alguns formatos somem. O Diagnóstico avisa. O YouTube também pode pedir confirmação anti-robô (“Sign in to confirm you’re not a bot”); o app mostra a mensagem sem tentar contornar.
- **Resoluções**: só são oferecidas as que a plataforma realmente lista. O rótulo usa o nome oficial (ex.: um vídeo 1920×788 aparece como “1080p”); nenhum upscale é feito.
- **MP4**: quando a resolução só existe em VP9/AV1, o app avisa que o MP4 pode não abrir em players antigos. “Formato original” mantém o contêiner da fonte sem converter.
- **MP3**: reconversão com perda a partir da fonte (geralmente AAC/Opus). Aumentar o bitrate não melhora a qualidade.
- **Retomada**: ao reabrir o navegador, trabalhos interrompidos voltam a “Aguardando” e retomam. O yt-dlp reaproveita arquivos `.part`; o download direto usa `Range` quando o servidor aceita; o gallery-dl pula arquivos já baixados. Não há garantia de retomada em todas as origens.
- **Ciclo de vida**: o aplicativo auxiliar só roda enquanto o Chrome está aberto (o Native Messaging o inicia e encerra). Downloads continuam com o popup fechado, mas não com o Chrome fechado.
- **DRM, paywalls e controles de acesso**: não são contornados.

## Sistemas operacionais

| Sistema | Pacote do helper | Instalador | Status |
|---|---|---|---|
| **macOS 26 (Darwin 25), Apple Silicon** | ✅ gerado (PyInstaller) e executado fora do venv | ✅ `install.sh`/`uninstall.sh` executados em HOME isolado; host lançado como o Chrome faz (origem em `argv[1]`) | **Testado**, exceto no **Chrome real** (ver abaixo) |
| macOS Intel | ❌ não gerado | — | Não testado |
| Linux | 🟡 o mesmo `scripts/package-helper.sh` deve funcionar; o código tem caminhos para Linux | 🟡 `install.sh` genérico | **Não testado** — precisa de validação em uma máquina Linux |
| Windows 10/11 | 🟡 o código usa `winreg` e modo binário do stdio, mas o `.exe` não foi gerado | 🟡 `install.ps1` / `uninstall.ps1` escritos | **Não testado** — precisa de validação em um Windows |

> **Chrome real**: o Chrome não está instalado neste computador, então a extensão **não foi carregada** em um navegador de verdade. O que foi testado: tipos (tsc), lógica da extensão e a ponte Native Messaging (`extension/src/native.ts`) falando com o helper real pelo mesmo enquadramento do protocolo; o empacotamento e a instalação. Não foram executados em navegador: a renderização da interface (popup/gerenciador), o menu de contexto e o selo. Veja `docs/TESTES.md`.
