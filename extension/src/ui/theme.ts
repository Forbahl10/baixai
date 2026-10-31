import { h, icon } from "./dom";

const KEY = "baixai-theme";
type Pref = "auto" | "light" | "dark";
const LABEL: Record<Pref, string> = { auto: "Tema: automático", light: "Tema: claro", dark: "Tema: escuro" };

function read(): Pref { const v = localStorage.getItem(KEY); return v === "light" || v === "dark" ? v : "auto"; }
function apply(p: Pref): void { if (p === "auto") delete document.documentElement.dataset["theme"]; else document.documentElement.dataset["theme"] = p; }

export function initTheme(): void { apply(read()); }

export function themeToggle(): HTMLButtonElement {
  const btn = h("button", { class: "btn btn-icon", type: "button" });
  const paint = () => {
    const p = read();
    btn.replaceChildren(icon(p === "dark" ? "moon" : "sun"));
    btn.setAttribute("aria-label", `${LABEL[p]} (clique para alternar)`);
    btn.title = LABEL[p];
  };
  btn.addEventListener("click", () => {
    const order: Pref[] = ["auto", "light", "dark"];
    const next = order[(order.indexOf(read()) + 1) % 3] ?? "auto";
    if (next === "auto") localStorage.removeItem(KEY); else localStorage.setItem(KEY, next);
    apply(next); paint();
  });
  paint();
  return btn;
}
