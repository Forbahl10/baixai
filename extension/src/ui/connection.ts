import type { BridgeState } from "../native";
import { announce, h, icon } from "./dom";
import type { UiClient } from "./client";

export const INSTALL_HELP_HASH = "#/ajuda";

export function extensionId(): string { return chrome.runtime.id; }

/** Chip compacto de estado, sempre com texto (não depende só de cor). */
export function mountStatusChip(root: HTMLElement, client: UiClient): void {
  const chip = h("span", { class: "chip", role: "status" });
  root.appendChild(chip);
  let last = "";
  client.onState((s) => {
    const [cls, text] =
      s.kind === "connected" ? ["chip-ok", `Aplicativo local conectado · v${s.hello.version}`]
      : s.kind === "connecting" || s.kind === "idle" ? ["chip-wait", "Conectando ao aplicativo local…"]
      : ["chip-err", "Aplicativo local não conectado"];
    chip.className = `chip ${cls}`;
    chip.replaceChildren(icon(s.kind === "connected" ? "check" : s.kind === "error" ? "alert" : "retry"), text);
    if (text !== last) { announce(text); last = text; }
  });
}

/** Cartão de instalação: aparece quando não há conexão com o aplicativo local. */
export function mountInstallBanner(root: HTMLElement, client: UiClient, opts: { compact: boolean }): void {
  const box = h("section", { class: "card card-warn", hidden: true, "aria-labelledby": "install-title" });
  root.appendChild(box);
  client.onState((s) => render(box, s, client, opts.compact));
}

function render(box: HTMLElement, s: BridgeState, client: UiClient, compact: boolean): void {
  box.hidden = s.kind !== "error";
  if (s.kind !== "error") return;
  const id = extensionId();
  const retry = h("button", { class: "btn", type: "button", on: { click: () => client.retryConnect() } }, icon("retry"), "Tentar novamente");
  const children: (Node | string)[] = [
    h("h2", { id: "install-title", class: "card-title", text: s.reason === "host_missing" ? "Instale o aplicativo auxiliar" : "Não foi possível conectar ao aplicativo local" }),
    h("p", { text: s.message }),
  ];
  if (s.reason === "host_missing" || s.reason === "forbidden") {
    children.push(
      h("p", { class: "muted", text: "Uma extensão sozinha não executa Python nem FFmpeg. Os downloads são feitos por um aplicativo auxiliar instalado no seu computador, que a extensão controla pelo Chrome." }),
      h("p", { class: "muted" }, "ID desta extensão (informe na instalação): ", h("code", { class: "inline-code", text: id })),
    );
  }
  const actions = h("div", { class: "row" }, retry);
  if (compact) actions.appendChild(h("a", { class: "btn btn-quiet", href: chrome.runtime.getURL("manager.html") + INSTALL_HELP_HASH, target: "_blank", rel: "noopener" }, "Como instalar"));
  else actions.appendChild(h("a", { class: "btn btn-quiet", href: INSTALL_HELP_HASH }, "Ver o passo a passo"));
  children.push(actions);
  box.replaceChildren(...children);
}
