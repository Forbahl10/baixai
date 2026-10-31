# Testes

## Como rodar

```sh
# Python (helper) — determinísticos, sem rede
.venv/bin/python -m pytest helper/tests

# TypeScript (extensão): tipos + testes (inclui integração com o helper real)
npx tsc -p extension/tsconfig.json --noEmit
node scripts/test-extension.mjs

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
| `extension/tests/*.test.ts` | extração de URLs, plataformas, validação de mensagens do host, ponte (conexão, erros do Chrome, timeouts, versão, eventos) e **integração com o helper real** |
| `test_live.py` | YouTube (análise, MP4, MP3), X (imagem), **cancelamento real** do yt-dlp, análise das demais plataformas |

## Resultados desta versão (30/10/2026, macOS arm64, Python 3.12, Node 22)

- Helper: **147 testes passando**, 1 ignorado quando não há FFmpeg no `PATH` (passa com `BAIXAI_FFMPEG`), 6 `live` desmarcados por padrão.
- Extensão: `tsc --noEmit` sem erros; **20 testes passando**.
- Live (links fornecidos pelo usuário): YouTube MP4+MP3 ✅, X imagem ✅, cancelamento real ✅. SoundCloud/TikTok/Instagram: **não executados** (nenhum link foi fornecido).
- Binário empacotado (PyInstaller): `--version`, `doctor`, análise do X e download real do YouTube (MP4 H.264+AAC 640×262) ✅ fora do venv.
- Instalador: `install.sh` → manifesto → host lançado como o Chrome faz → `uninstall.sh --purge-data` ✅ (HOME isolado).

## O que NÃO foi testado

- **Extensão em um Chrome real** (carregamento, popup, gerenciador, menu de contexto, selo de atividade, Native Messaging do navegador). A interface foi verificada por tipos e lógica, não visualmente.
- Linux e Windows (helper, instaladores, registro no Windows).
- Instagram, TikTok, SoundCloud, vídeo em post do X, playlists.
- Acessibilidade com leitor de tela (foco visível, rótulos, `aria-live` e `role=progressbar` foram implementados, sem auditoria com ferramentas).
- Assinatura/notarização do macOS e dos instaladores.
