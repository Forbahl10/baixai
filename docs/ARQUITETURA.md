# Arquitetura

```
┌────────────────────────── Chrome ───────────────────────────┐        ┌──────── seu computador ────────────────────┐
│ popup.html / manager.html  ──port──▶  service worker         │ stdio  │  baixai-helper (Python)                     │
│ (TypeScript, MV3)                     NativeBridge ──────────┼───────▶│  host.py → service.py → fila SQLite         │
│ permissões: nativeMessaging,          (connectNative,        │ 32-bit │       ├─ engines/ytdlp.py     (yt-dlp)      │
│ contextMenus, activeTab               hello/protocolo 1)     │ + JSON │       ├─ engines/gallerydl.py (gallery-dl)  │
└──────────────────────────────────────────────────────────────┘        │       ├─ engines/direct.py    (HTTP seguro) │
                                                                        │       └─ FFmpeg / Pillow (conversões)       │
                                                                        └─────────────────────────────────────────────┘
```

Nenhum servidor público participa. Nenhuma porta de rede é aberta pelo aplicativo auxiliar.

## Por que Native Messaging (e não HTTP local)

- O Chrome só inicia o host se o **ID da extensão** estiver em `allowed_origins` no manifesto do host; o host ainda confere a origem recebida em `argv[1]` contra `host_config.json` (defesa em profundidade).
- Não há porta aberta: páginas web externas não têm como chamar o aplicativo (um servidor em `127.0.0.1` exigiria autenticação, validação de `Origin`/`Host` e proteção contra DNS rebinding — complexidade desnecessária).
- Limites respeitados: host→Chrome ≤ 1 MB (saída limitada a 900 KB, com redução automática de listas longas) e Chrome→host ≤ 64 MiB (entrada limitada a 256 KiB). **Nenhum arquivo de mídia passa pelo canal**: só comandos, status e progresso (≤ 4 eventos/s por trabalho).
- Ciclo de vida: `connectNative` mantém o service worker vivo enquanto a porta está aberta; sem páginas abertas e sem trabalhos ativos por 90 s, a porta é fechada e o host encerra.

## Protocolo (versão 1)

Requisição `{ "id", "cmd", "payload" }` → resposta `{ "id", "ok", "data" | "error" }`; eventos assíncronos `{ "event": "job" | "removed" | "cleared" | "fatal", … }`.
Comandos: `hello`, `analyze`, `enqueue`, `enqueue_batch`, `list_jobs`, `cancel`, `retry`, `remove`, `reveal`, `job_log`, `clear_history`, `get_settings`, `set_settings`, `choose_folder`, `tools_status`, `tools_check_updates`, `tools_update_ytdlp`.
Os dois lados validam: o helper (`protocol.py`, esquema estrito: campos desconhecidos, tipos, intervalos e enums são rejeitados) e a extensão (`parseHostMessage` descarta o que não tem o formato esperado). O service worker só aceita portas das próprias páginas da extensão e só repassa comandos da lista.

## Mecanismos (adaptadores independentes)

Cada um implementa `analyze(url, …)` e `download(spec, outdir, ctx)`; a fila não conhece os detalhes.

| Adaptador | Usa | Quando |
|---|---|---|
| `ytdlp` | yt-dlp | vídeo/áudio (YouTube, SoundCloud, reels, TikTok, vídeos do X) |
| `gallerydl` | gallery-dl | imagens/galerias (X, Instagram, TikTok fotos) |
| `direct` | HTTP próprio | URL que é diretamente uma imagem/áudio/vídeo |

A seleção (`platforms.detect`) devolve a **ordem de tentativa**: ex. post do X → `ytdlp`, depois `gallerydl`; `instagram.com/p/…` → `gallerydl`, depois `ytdlp`. Se o primeiro mecanismo falha com “sem mídia”/“não suportado”, o próximo é tentado; erros mais informativos (login, indisponível, rede) têm prioridade na mensagem final.

Atualização: yt-dlp e gallery-dl rodam como **subprocessos** (`python -m yt_dlp`, ou `baixai-helper --engine yt-dlp` no executável empacotado). É possível apontar para outros executáveis nas configurações, ou usar `tools update-ytdlp` (ação explícita, com SHA-256 oficial) que instala um binário em `…/Baixai/engines/`. Nada é baixado em silêncio.

## Fila

SQLite (WAL) em `…/Baixai/baixai.db`. Estados: `waiting → analyzing → downloading ⇄ converting → done | failed | cancelled`.

- **Concorrência** limitada (1–5, padrão 2); despachante em thread própria.
- **Persistência/recuperação**: ao iniciar, trabalhos em `analyzing/downloading/converting` voltam a `waiting` (“Retomando após reinício”). No encerramento limpo, os trabalhos são interrompidos e também ficam `waiting`.
- **Cancelamento**: flag cooperativa + `SIGTERM` ao grupo de processos (e `SIGKILL` após 3 s); a pasta temporária é apagada antes de publicar o estado `cancelled`.
- **Duplicação**: chave = SHA-256 de (URL normalizada, modo, opções). Item igual ativo → devolve o existente; igual já concluído → pede confirmação (`force`).
- **Arquivos**: cada trabalho baixa em `<destino>/.baixai-tmp/<id>/` (mesmo volume → mover é atômico; `.part` sobrevive a reinícios). Ao concluir, os arquivos são movidos para `<destino>/[plataforma]/[autor]/` com nomes sanitizados e **sem sobrescrever** (`nome (1).ext`). `safe_join` resolve o caminho final e recusa qualquer coisa fora da pasta de destino.
- **Progresso**: real quando o mecanismo informa (yt-dlp: bytes/total por faixa; gallery-dl: arquivos concluídos ÷ itens selecionados); caso contrário, estado indeterminado.

## Segurança

| Risco | Mitigação |
|---|---|
| Injeção de comando | `subprocess.Popen(lista, shell=False)`; a URL vai depois de `--`; testes com URL maliciosa |
| SSRF / rede local | só `http(s)`, sem credenciais, portas 80/443, sem hosts de rede local, **todos** os IPs resolvidos precisam ser públicos (inclui IPv6 e IPv4 mapeado); formas ofuscadas (`2130706433`, `0x7f.1`) caem na resolução; hosts de plataformas ficam numa lista permitida e o **extrator genérico do yt-dlp é desligado** (`--use-extractors default,-generic`) |
| Redirecionamentos | no download direto cada salto é revalidado e a conexão é **fixada no IP validado** (anti-DNS-rebinding). Para yt-dlp/gallery-dl os redirecionamentos são deles: o risco fica limitado aos hosts da lista permitida |
| Path traversal | `sanitize_component/filename`, `safe_join`, `unique_path`; a extensão nunca envia caminhos de arquivo |
| Origem | `allowed_origins` + conferência em `argv[1]`; sem `externally_connectable`, sem content scripts |
| Ambiente dos subprocessos | variáveis permitidas por lista (sem `PYTHON*`, sem segredos do ambiente); `--ignore-config` no yt-dlp e `--config-ignore` no gallery-dl |
| Segredos em logs/UI | `redact()` remove query strings, `Authorization`, cookies, tokens e o diretório home; erros são traduzidos (`friendly.py`) |
| Credenciais | **nenhuma coletada**; sem `--cookies-from-browser` |
| Extensão | CSP restritiva, DOM sempre por `textContent` (títulos vêm de sites), sem `eval`, sem código remoto |

### Autenticação futura (projeto, não implementada)

Se for necessária no futuro, deve ser **opt-in explícita** por plataforma: o usuário escolhe um arquivo de cookies (ou faz login em uma janela isolada do app), o conteúdo é guardado no chaveiro do sistema (Keychain/DPAPI/libsecret), nunca em log ou no banco, e é passado ao mecanismo por arquivo temporário com permissão `0600` removido ao final. Cada uso mostraria qual conta está ativa. Isso não faz parte do MVP.

## Layout do repositório

```
extension/   TypeScript MV3 (src/, public/, manifest.template.json, tests/)
helper/      Python (baixai_helper/, tests/, pyproject.toml, entry.py)
packaging/   instaladores (sh/ps1), LEIA-ME, oferta de código-fonte
scripts/     build da extensão, pacote do helper, ícones, inventário, site
site/        página estática de apresentação e download
docs/        arquitetura, matriz, testes, privacidade, Chrome Web Store
```
