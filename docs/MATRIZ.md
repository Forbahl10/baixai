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
- **YouTube e runtime JavaScript**: o yt-dlp precisa de Deno ou Node.js 22+ para resolver os desafios do YouTube. Sem isso, alguns formatos somem. O instalador oferece baixar o Deno (SHA-256 conferido) e o `baixai doctor` avisa se faltar. O YouTube também pode pedir confirmação anti-robô (“Sign in to confirm you’re not a bot”); o app mostra a mensagem sem tentar contornar.
- **Resoluções**: só são oferecidas as que a plataforma realmente lista. O rótulo usa o nome oficial (ex.: um vídeo 1920×788 aparece como “1080p”); nenhum upscale é feito.
- **MP4**: quando a resolução só existe em VP9/AV1, o app avisa que o MP4 pode não abrir em players antigos. “Formato original” mantém o contêiner da fonte sem converter.
- **MP3**: reconversão com perda a partir da fonte (geralmente AAC/Opus). Aumentar o bitrate não melhora a qualidade.
- **Retomada**: ao reabrir o navegador, trabalhos interrompidos voltam a “Aguardando” e retomam. O yt-dlp reaproveita arquivos `.part`; o download direto usa `Range` quando o servidor aceita; o gallery-dl pula arquivos já baixados. Não há garantia de retomada em todas as origens.
- **Ciclo de vida (só na extensão do Chrome, opcional)**: o aplicativo auxiliar só roda enquanto o Chrome está aberto (o Native Messaging o inicia e encerra). Downloads continuam com o popup fechado, mas não com o Chrome fechado.
- **DRM, paywalls e controles de acesso**: não são contornados.

## Sistemas operacionais

O uso principal agora é pelo terminal (`baixai "LINK"`), instalado por `get.sh` / `get.ps1`. A coluna "Como foi verificado" separa o que rodou **numa máquina real** do que rodou **só na integração contínua** (runners do GitHub Actions; ver `.github/workflows/build.yml`).

| Sistema | Pacote | Como foi verificado | Não verificado |
|---|---|---|---|
| **macOS Apple Silicon** | ✅ PyInstaller | **Máquina real**: instalação pelo `get.sh` contra uma Release simulada, perguntas do instalador (PATH em `~/.zshrc`, reinstalar sem duplicar, desinstalar), FFmpeg e Deno reais com SHA-256, downloads reais (YouTube MP4 e MP3, imagem do X em PNG) e conversões. Também na CI. | Assinatura/notarização |
| macOS Intel | ✅ gerado na CI | **Só CI** (`macos-15-intel`): `get.sh`, FFmpeg real, conversões WAV→MP3 e PNG→JPEG locais, comando `baixai`, desinstalação. | Máquina física; links reais; perguntas interativas |
| Linux x86_64 | ✅ gerado na CI | **Só CI** (Ubuntu): o mesmo roteiro do macOS Intel. | Distribuições além do Ubuntu; links reais; perguntas interativas |
| Windows 10/11 x86_64 | ✅ `.exe` gerado na CI | **Só CI** (`windows-latest`): `get.ps1`, FFmpeg real (Gyan), conversões locais, comando `baixai.cmd`, desinstalação. | PC físico e Windows 10; **PATH do usuário (a CI usa `-NoPath`)**; perguntas interativas; nomes de usuário com acento; links reais |
| Linux arm64 / Windows arm64 | ❌ sem pacote | Há builds de FFmpeg/Deno verificados na tabela de `deps.py`, mas nenhum pacote foi gerado. No Windows ARM, o `.exe` x64 deveria rodar por emulação (não testado). | Tudo |

**Deno**: a CI já tem Node instalado, então o instalador (que só baixa o que falta) o pularia; por isso o teste de fumaça força `tools install-deno` em todos os sistemas e confere que o Deno passa a ser o runtime preferido.

> **Chrome real** (extensão, opcional): o Chrome não está instalado neste computador, então a extensão **não foi carregada** em um navegador de verdade. O que foi testado: tipos (tsc), lógica da extensão e a ponte Native Messaging (`extension/src/native.ts`) falando com o helper real pelo mesmo enquadramento do protocolo; o empacotamento e a instalação. Não foram executados em navegador: a renderização da interface (popup/gerenciador), o menu de contexto e o selo. Veja `docs/TESTES.md`.
