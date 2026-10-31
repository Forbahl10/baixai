# Lista de permissões e justificativas

`manifest.json` (versão 0.1.0):

| Permissão | Por que é necessária | Quando é usada |
|---|---|---|
| `nativeMessaging` | Única forma suportada de a extensão conversar com o aplicativo auxiliar local (Chrome ↔ processo no computador) sem abrir portas de rede. | Ao abrir o popup/gerenciador e ao enviar comandos (analisar, enfileirar, cancelar). |
| `contextMenus` | Itens “Analisar link com o Baixaí” (clique direito em links das plataformas compatíveis) e “Analisar esta página com o Baixaí”. | Apenas quando o usuário clica no menu. |
| `activeTab` | Ler o endereço da aba atual **somente** quando o usuário abre o popup e clica em “Usar aba atual”. Evita pedir acesso permanente a todas as abas. | Apenas após ação do usuário. |

Não solicitados: `tabs`, `storage`, `cookies`, `history`, `downloads`, `notifications`, `webRequest`, `<all_urls>` ou qualquer permissão de host; sem content scripts; sem `externally_connectable`; sem `optional_permissions` nesta versão.

Outros itens:
- **Código remoto**: nenhum. Todo o JavaScript é compilado de TypeScript e empacotado (`build/extension-store`). CSP: `script-src 'self'; object-src 'none'; connect-src 'none'; …`.
- **Minificação/ofuscação**: não minificado (o código enviado é legível).
- **Dados do usuário (formulário de privacidade)**: a extensão trata *atividade na web* apenas no sentido de links que o usuário fornece e o endereço da aba atual sob demanda; esses dados vão somente ao aplicativo local. Nenhum dado é transmitido a servidores do desenvolvedor. Marque as declarações de acordo com `docs/PRIVACIDADE.md` e **revise os rótulos do painel** (não verificado automaticamente).
