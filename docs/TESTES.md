# Testes

## Como rodar

```sh
# Python (helper) — determinísticos, sem rede
.venv/bin/python -m pytest helper/tests

# TypeScript (extensão): tipos + testes (inclui integração com o helper real)
npx tsc -p extension/tsconfig.json --noEmit
node scripts/test-extension.mjs

# Pacote final, do jeito do usuário (get.sh/get.ps1 contra uma Release simulada; baixa FFmpeg e Deno reais)
.venv/bin/python scripts/package_helper.py && .venv/bin/python scripts/smoke_package.py dist

# Integração REAL (rede + plataformas). Use apenas conteúdo próprio ou autorizado.
BAIXAI_LIVE_YOUTUBE="<link>" BAIXAI_LIVE_X_IMAGE="<link>" \
BAIXAI_LIVE_SOUNDCLOUD="<link>" BAIXAI_LIVE_TIKTOK="<link>" BAIXAI_LIVE_INSTAGRAM="<link>" \
  .venv/bin/python -m pytest helper/tests/test_live.py -m live
```

Os testes `live` ficam fora da execução padrão (`-m 'not live'`) e são ignorados se a variável do link não existir.

## O que cada arquivo cobre

| Arquivo | Cobre |
|---|---|
| `test_urlsafe.py` | validação de URL (esquemas, credenciais, portas, hosts locais, IPs privados/loopback/link-local/CGNAT/IPv6/mapeado, formas ofuscadas), **bloqueio de redirecionamento** para rede interna |
| `test_platforms.py` | detecção de plataforma/tipo/mecanismo, domínios imitadores, links não suportados com orientação |
| `test_protocol.py` | enquadramento (UTF-8, EOF, truncado, JSON inválido), limite de entrada e de saída (1 MB), validação de esquema (campos desconhecidos, tipos, intervalos) |
| `test_args_parsers.py` | **construção segura de argumentos** (`--` antes da URL, URL maliciosa como um único argumento, sem cookies, extrator genérico desligado), seletores de formato, parsers de yt-dlp/gallery-dl com fixtures, mapeamento de erros sem vazar segredos |
| `test_sanitize_redact.py` | sanitização de nomes (traversal, reservados do Windows, ocultos, bytes), `safe_join` com symlink, não sobrescrever, redação de logs |
| `test_queue.py` | fluxo completo, **falha e repetição**, exceção inesperada, **cancelamento** (em andamento e aguardando), limite de concorrência, **duplicação**, **recuperação após reinício**, remover/limpar histórico (sem apagar arquivos), logs redigidos |
| `test_convert_install.py` | JPEG com transparência (aviso + fundo branco), PNG, conversão inválida mantém o original; instalação/remoção do manifesto, IDs inválidos |
| `test_host_e2e.py` | **host real em subprocesso** via protocolo: `hello`, origem não autorizada, mensagens inválidas, fluxo completo com servidor HTTP local (redirecionamento + conversão), cancelamento, **fila sobrevive a `kill -9`**, rede local bloqueada, áudio direto → MP3 |
| `test_terminal_deps.py` | comando `baixai "LINK"` sem subcomando, escolha de modo/qualidade/bitrate/formato, listas e galerias (`--tudo`, `--itens`, confirmação), **instalador de FFmpeg/Deno**: tabelas por plataforma com SHA-256, extração só pelo nome-base (sem path traversal), download com checksum inválido recusado |
| `scripts/smoke_package.py` | **pacote final em máquina limpa** (macOS, Linux, Windows): `get.sh`/`get.ps1`, SHA-256 do pacote (adulterado é recusado), FFmpeg e Deno reais, `baixai doctor`, motores embutidos, WAV→MP3 e PNG→JPEG por link, links perigosos recusados, desinstalação sem sobras |
| `extension/tests/*.test.ts` | extração de URLs, plataformas, validação de mensagens do host, ponte (conexão, erros do Chrome, timeouts, versão, eventos) e **integração com o helper real** |
| `test_live.py` | YouTube (análise, MP4, MP3), X (imagem), **cancelamento real** do yt-dlp, análise das demais plataformas |

## Resultados desta versão (30/10/2026)

- Helper: **169 testes passando** em macOS, Linux e Windows (CI); 1 ignorado sem FFmpeg no `PATH`, 6 `live` desmarcados por padrão.
- Extensão: `tsc --noEmit` sem erros; **20 testes passando**.
- **Teste de fumaça do pacote** (`scripts/smoke_package.py`): passou na CI em macOS Apple Silicon, macOS Intel, Linux x86_64 e Windows x86_64, e numa máquina real (macOS Apple Silicon).
- Live (links fornecidos pelo usuário), em macOS Apple Silicon, com o **comando instalado** (`baixai`) e só o Deno baixado pelo instalador (sem Node no `PATH`): YouTube vídeo MP4 H.264+AAC ✅, YouTube áudio MP3 ✅, post do X com imagem convertida para PNG ✅. SoundCloud/TikTok/Instagram: **não executados**.
- **Comando público de ponta a ponta** (v0.1.1, Mac real, HOME isolado, sem ferramentas do sistema): `curl ... get.sh | sh` baixou do GitHub, conferiu o SHA-256, baixou FFmpeg e Deno, `baixai doctor` "Tudo certo", e os downloads reais funcionaram (YouTube MP4 e MP3, imagem do X em JPEG, **link direto por HTTPS**).
- **Lição da v0.1.0**: o pacote construído na CI passou em todos os testes da CI, mas falhava em qualquer outra máquina ao baixar por HTTPS, porque o Python da CI guardava os certificados num caminho que só existe lá. Corrigido (certifi embutido) e o teste de fumaça passou a rodar **sem certificados do sistema** para detectar isso.
- Instalador interativo (Mac, terminal simulado em HOME isolado): PATH só com consentimento, sem duplicar ao reinstalar, desinstalador remove somente as linhas dele ✅.

## O que NÃO foi testado

- **Extensão em um Chrome real** (carregamento, popup, gerenciador, menu de contexto, selo de atividade, Native Messaging do navegador). A interface foi verificada por tipos e lógica, não visualmente.
- Linux e Windows **fora da CI**: nenhuma máquina física. No Windows, também não foram testados o PATH do usuário (a CI usa `-NoPath`), as perguntas interativas e nomes de usuário com acento. Idem para as perguntas interativas no Linux e no macOS Intel.
- Links reais em Linux, Windows e macOS Intel (a CI usa mídia servida localmente).
- Instagram, TikTok, SoundCloud, vídeo em post do X, playlists.
- Acessibilidade com leitor de tela (foco visível, rótulos, `aria-live` e `role=progressbar` foram implementados, sem auditoria com ferramentas).
- Assinatura/notarização do macOS e dos instaladores.
