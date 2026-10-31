# Política de Privacidade — Baixaí

*Última atualização: 30/10/2026. Versão do produto: 0.1.0.*

O Baixaí é uma extensão do Chrome com um aplicativo auxiliar que roda **no seu computador**. Esta política descreve exatamente o que o produto faz com dados, de acordo com o comportamento implementado.

## Resumo

- **Sem telemetria, sem contas, sem anúncios, sem venda de dados.** Não existe servidor do Baixaí que receba dados seus.
- **Nada do seu histórico de navegação é coletado.** A extensão só lê o endereço da aba atual quando você clica em “Usar aba atual”, e o menu de contexto só usa o link em que você clicou.
- **Senhas, cookies e logins não são lidos nem usados.** O produto baixa apenas conteúdo público.

## Dados tratados e para quê

| Dado | Quando | Para quê | Onde fica |
|---|---|---|---|
| Links que você cola, o endereço da aba atual (apenas ao clicar) ou o link do menu de contexto | quando você pede uma análise ou download | identificar a mídia e baixá-la | enviado **somente ao aplicativo auxiliar no seu computador**; o app acessa o site de origem (por exemplo, YouTube) para obter o conteúdo, como o seu navegador faria |
| Título, autor, miniatura e formatos do conteúdo | durante a análise | mostrar a prévia e as opções | memória e fila local |
| Fila e histórico de downloads (links, opções, estado, caminhos dos arquivos) | enquanto existirem | retomar a fila após reiniciar e mostrar o histórico | banco SQLite local: `~/Library/Application Support/Baixai` (macOS), `%APPDATA%\Baixai` (Windows), `~/.local/share/baixai` (Linux) |
| Registros (logs) de execução | durante os downloads | diagnóstico de falhas | arquivos locais, com query strings, tokens e cookies removidos; no máximo ~3 MB |
| Preferências (pasta, formatos, concorrência) | quando você salva | lembrar suas escolhas | banco local; o tema da interface fica no armazenamento local da extensão |

## Conexões de rede

- O aplicativo auxiliar conecta-se **às plataformas de onde você escolheu baixar** (e aos servidores de mídia delas).
- A interface da extensão carrega **miniaturas diretamente dos servidores da plataforma** (como qualquer página que exiba a imagem). Isso revela seu endereço IP a esses servidores, como ocorre ao navegar nelas.
- O aplicativo conecta-se ao **GitHub** (`api.github.com`, `github.com`) **somente** se você clicar em “Verificar atualização” ou “Atualizar o yt-dlp” no Diagnóstico.
- Se você aceitar, o instalador baixa o FFmpeg de um servidor de terceiros indicado na tela, uma única vez.
- Nenhuma outra conexão é feita. A extensão não carrega nem executa código remoto.

## Controle e exclusão

- **Limpar histórico**: aba Downloads → “Limpar histórico” (arquivos baixados não são apagados).
- **Remover tudo**: `./uninstall.sh --purge-data` (ou `.\uninstall.ps1 -PurgeData`) apaga fila, histórico, logs e preferências do aplicativo; remover a extensão em `chrome://extensions` apaga o que ela guarda no navegador.
- Os arquivos que você baixa ficam na pasta que você escolheu e são seus.

## Uso responsável

Baixe apenas conteúdo próprio, autorizado ou permitido pelo autor, pela licença ou pelos termos da plataforma. O Baixaí não contorna DRM, paywalls ou controles de acesso. É um projeto independente, sem parceria, patrocínio ou aprovação das plataformas citadas.

## Crianças

O produto não é direcionado a crianças e não coleta dados pessoais.

## Mudanças e contato

Alterações relevantes serão descritas aqui antes de entrarem em vigor. Contato do responsável: abra uma _issue_ em https://github.com/Forbahl10/baixai/issues (não coletamos e-mail).
