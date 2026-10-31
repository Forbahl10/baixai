# Checklist de submissão à Chrome Web Store

**Estado: NADA foi enviado nem publicado.** Os artefatos abaixo estão prontos; os itens pendentes dependem de conta, hospedagem e revisão humana.

## Pronto (gerado neste repositório)
- [x] ZIP da extensão sem o campo `key`: `dist/baixai-extension-0.1.0.zip` (Manifest V3, ícones 16/32/48/128).
- [x] Permissões mínimas justificadas (`permissoes.md`).
- [x] Texto de apresentação em pt-BR (`listagem-ptbr.md`).
- [x] Política de privacidade em arquivo (`docs/PRIVACIDADE.md`) e em HTML (`site/privacidade.html`).
- [x] Sem código remoto, sem `eval`, sem ofuscação.
- [x] Pacote e instalador do aplicativo auxiliar para macOS arm64, avisos de terceiros e código-fonte.

## Pendente — precisa de você
- [ ] Conta de desenvolvedor da Chrome Web Store (taxa única de registro e verificação em duas etapas obrigatória).
- [ ] **Hospedar** `site/` (por exemplo GitHub Pages ou domínio próprio) e usar o endereço como site, suporte e **URL da política de privacidade** no painel.
- [ ] **Hospedar os pacotes do helper** (`dist/*.tar.gz`, `SHA256SUMS.txt`, `baixai-source-*.tar.gz`) para o link de download do site funcionar.
- [ ] Preencher o e-mail de contato em `docs/PRIVACIDADE.md`, `site/privacidade.html` e no painel.
- [ ] **Capturas de tela** 1280×800 (ou 640×400) tiradas da extensão rodando num Chrome real — não foi possível gerá-las aqui. Use conteúdo próprio/livre.
- [ ] Ícone promocional (opcional): tile pequeno 440×280.
- [ ] Preencher as declarações de privacidade do painel (finalidade única, justificativa de cada permissão, uso de dados, “não vendo dados”, “não uso para fins não relacionados”, “não uso para crédito”).
- [ ] **ID de produção**: ao criar o item, a loja atribui o ID. Rode o instalador do helper com `--extension-id <ID de produção>` (e inclua o ID em `packaging/DEFAULT_EXTENSION_IDS` das próximas versões).
- [ ] **Assinar/notarizar** o aplicativo auxiliar (Apple Developer ID + notarização no macOS; assinatura de código no Windows). Sem isso, o macOS/Windows podem exibir alertas; o instalador remove a quarentena apenas porque você o executa manualmente.
- [ ] Testar em um Chrome real (macOS, Windows, Linux) antes de enviar.
- [ ] Conferir as políticas vigentes no momento do envio.

## Riscos de revisão a considerar (não verificados com a loja)
- As políticas do programa dizem, em resumo, para **não encorajar, facilitar ou habilitar o download não autorizado de conteúdo protegido por direitos autorais** e que **baixadores de vídeo podem ficar sem destaque**; extensões desse tipo costumam receber revisão rigorosa e podem ser recusadas — especialmente se a descrição ou as capturas de tela citarem o YouTube ou outras plataformas de forma que sugira uso não autorizado. A descrição deste repositório foi escrita para enfatizar uso autorizado, mas **a aprovação não é garantida**.
- A extensão depende de um aplicativo externo: a descrição declara isso de forma clara e não oculta a dependência; confirme se há exigências específicas da loja para aplicativos complementares.
- Se a loja recusar, a alternativa é distribuir o ZIP para carregamento manual (modo desenvolvedor) ou por política corporativa, o que o site já documenta.

## Texto para “Instruções de teste” do revisor
Instale o aplicativo auxiliar (link no site; macOS: `./install.sh --extension-id <ID>`), reinicie o Chrome, abra a extensão: o indicador deve mostrar “Aplicativo local conectado”. Cole um link de conteúdo livre (por exemplo, uma imagem de domínio público) e clique em Analisar → Adicionar à fila.
