import { h } from "./dom";

const code = (t: string) => h("code", { class: "inline-code", text: t });
const pre = (t: string) => h("pre", { class: "codeblock", tabindex: 0 }, h("code", { text: t }));

export function mountHelp(root: HTMLElement): void {
  const id = chrome.runtime.id;
  root.append(
    h("section", { class: "card" }, h("h2", { class: "card-title", text: "Como funciona" }),
      h("p", { text: "O Baixaí tem duas partes: esta extensão (a interface no Chrome) e um aplicativo auxiliar que roda no seu computador. A extensão sozinha não executa Python nem FFmpeg — por isso o aplicativo auxiliar precisa ser instalado separadamente." }),
      h("p", { class: "muted", text: "Nenhum servidor público processa seus downloads: tudo acontece na sua máquina, e a extensão conversa com o aplicativo pelo Chrome (Native Messaging)." })),
    h("section", { class: "card" }, h("h2", { class: "card-title", text: "Instalação em 3 passos" }),
      h("ol", { class: "steps" },
        h("li", {}, h("strong", { text: "Baixe o aplicativo auxiliar " }), "para o seu sistema na página de download do Baixaí e extraia o arquivo."),
        h("li", {}, h("strong", { text: "Execute o instalador " }), "informando o ID desta extensão:", h("p", {}, "ID desta extensão: ", code(id)),
          h("p", { class: "muted", text: "macOS / Linux (Terminal, dentro da pasta extraída):" }), pre(`./install.sh --extension-id ${id}`),
          h("p", { class: "muted", text: "Windows (PowerShell, dentro da pasta extraída):" }), pre(`.\\install.ps1 -ExtensionId ${id}`)),
        h("li", {}, h("strong", { text: "Reinicie o Chrome " }), "e abra o Baixaí de novo. O indicador deve mostrar “Aplicativo local conectado”. Se não, veja a aba Diagnóstico.")),
      h("p", { class: "muted", text: "Para remover: execute ./uninstall.sh (ou .\\uninstall.ps1). A extensão pode ser removida em chrome://extensions." })),
    h("section", { class: "card" }, h("h2", { class: "card-title", text: "FFmpeg e YouTube" }),
      h("ul", {}, h("li", {}, h("strong", { text: "FFmpeg " }), "é necessário para MP3, para combinar vídeo e áudio e para algumas conversões. O instalador pergunta antes de baixá-lo; você também pode instalar por conta própria."),
        h("li", {}, h("strong", { text: "Deno ou Node.js 22+ " }), "ajudam o YouTube a funcionar completamente (alguns formatos dependem disso)."))),
    h("section", { class: "card card-note" }, h("h2", { class: "card-title", text: "Use com responsabilidade" }),
      h("ul", {}, h("li", { text: "Baixe apenas conteúdo próprio, autorizado ou permitido pelo autor, pela licença ou pelos termos da plataforma." }),
        h("li", { text: "O Baixaí não contorna DRM, paywalls ou controles de acesso, e não usa seu login ou cookies." }),
        h("li", { text: "O Baixaí é independente e não tem parceria nem aprovação do YouTube, Instagram, TikTok, X ou SoundCloud." }),
        h("li", { text: "Nem todo tipo de link funciona em toda plataforma: o aplicativo mostra só as opções realmente disponíveis para cada link." }))),
    h("section", { class: "card" }, h("h2", { class: "card-title", text: "Privacidade" }),
      h("p", { text: "Sem telemetria, sem contas e sem coleta do seu histórico de navegação. A extensão só lê o endereço da aba atual quando você clica em “Usar aba atual”, e o menu de contexto só envia o link em que você clicou. Os links vão apenas ao aplicativo local, que os usa para falar com a plataforma de origem." })));
}
