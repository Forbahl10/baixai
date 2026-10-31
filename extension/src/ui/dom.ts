/** Criação de DOM segura: sempre textContent, nunca innerHTML (títulos vêm de sites externos). */
export type Child = Node | string | number | null | undefined | false;
type Props = {
  class?: string; text?: string; on?: Record<string, (ev: Event) => void>;
  [attr: string]: string | number | boolean | Record<string, (ev: Event) => void> | undefined;
};

export function h<K extends keyof HTMLElementTagNameMap>(tag: K, props: Props = {}, ...children: Child[]): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === undefined || v === false) continue;
    if (k === "class") el.className = String(v);
    else if (k === "text") el.textContent = String(v);
    else if (k === "on") for (const [ev, fn] of Object.entries(v as Record<string, (e: Event) => void>)) el.addEventListener(ev, fn);
    else if (k === "value" || k === "checked" || k === "disabled" || k === "hidden" || k === "open") (el as unknown as Record<string, unknown>)[k] = v;
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  append(el, children);
  return el;
}
export function append(el: Node, children: Child[]): void {
  for (const c of children) if (c !== null && c !== undefined && c !== false) el.appendChild(typeof c === "object" ? c : document.createTextNode(String(c)));
}
export function clear(el: Node): void { while (el.firstChild) el.removeChild(el.firstChild); }
export function $<T extends HTMLElement>(sel: string, root: ParentNode = document): T {
  const el = root.querySelector<T>(sel);
  if (!el) throw new Error(`Elemento não encontrado: ${sel}`);
  return el;
}

let liveEl: HTMLElement | null = null;
/** Anuncia uma mensagem para leitores de tela (região aria-live). */
export function announce(msg: string): void {
  if (!liveEl) {
    liveEl = h("div", { class: "sr-only", role: "status", "aria-live": "polite" });
    document.body.appendChild(liveEl);
  }
  liveEl.textContent = "";
  setTimeout(() => { if (liveEl) liveEl.textContent = msg; }, 30);
}

export function icon(name: "download" | "check" | "alert" | "x" | "folder" | "retry" | "trash" | "link" | "sun" | "moon" | "logs" | "external"): SVGSVGElement {
  const paths: Record<string, string> = {
    download: "M12 3v12m0 0l-4-4m4 4l4-4M5 19h14", check: "M5 13l4 4L19 7", alert: "M12 8v5m0 3h.01M10.3 3.9L2.4 18a2 2 0 001.7 3h15.8a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
    x: "M6 6l12 12M18 6L6 18", folder: "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z", retry: "M20 12a8 8 0 10-2.3 5.7M20 5v5h-5",
    trash: "M4 7h16M10 11v6m4-6v6M6 7l1 12a2 2 0 002 2h6a2 2 0 002-2l1-12M9 7V4h6v3", link: "M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1",
    sun: "M12 4V2m0 20v-2m8-8h2M2 12h2m13.7-5.7l1.4-1.4M4.9 19.1l1.4-1.4m0-11.4L4.9 4.9m14.2 14.2l-1.4-1.4M12 8a4 4 0 100 8 4 4 0 000-8z",
    moon: "M21 13A9 9 0 1111 3a7 7 0 0010 10z", logs: "M5 5h14M5 10h14M5 15h9M5 20h6", external: "M14 4h6v6m0-6L10 14M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5",
  };
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("aria-hidden", "true"); svg.setAttribute("class", "icon");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", paths[name] ?? ""); svg.appendChild(p);
  return svg;
}
