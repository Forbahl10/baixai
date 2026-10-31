import type { Hello, ToolsStatus } from "../protocol";
import { announce, h, icon } from "./dom";
import { errorText, type UiClient } from "./client";

export function mountDiagnostics(root: HTMLElement, client: UiClient): void {
  const body = h("div", { class: "diag" });
  const msg = h("p", { class: "status", role: "status", "aria-live": "polite" });
  root.append(body, msg);

  const badge = (ok: boolean, okText: string, badText: string) => h("span", { class: `pill ${ok ? "pill-ok" : "pill-bad"}` }, icon(ok ? "check" : "alert"), ok ? okText : badText);
  const rowOf = (name: string, status: Node, detail: string) => h("tr", {}, h("th", { scope: "row", text: name }), h("td", {}, status), h("td", { class: "muted", text: detail }));

  async function load(refresh = false): Promise<void> {
    if (client.state.kind !== "connected") { paintDisconnected(); return; }
    try {
      const hello = await client.call<Hello>("hello");
      const { tools } = await client.call<{ tools: ToolsStatus }>("tools_status", { refresh });
      paint(hello, tools);
    } catch (e) { msg.className = "status status-error"; msg.textContent = errorText(e); }
  }
  function paintDisconnected(): void {
    const s = client.state;
    body.replaceChildren(h("p", { class: "notice" }, icon("alert"), s.kind === "error" ? s.message : "Conectando ao aplicativo local…"),
      h("p", { class: "muted", text: "Sem conexão, só é possível verificar o ID da extensão. Siga o passo a passo na aba Ajuda." }),
      h("p", {}, "ID da extensão: ", h("code", { class: "inline-code", text: chrome.runtime.id })),
      h("button", { class: "btn", type: "button", on: { click: () => client.retryConnect() } }, icon("retry"), "Tentar novamente"));
  }
  client.onState(() => void load());

  function paint(hello: Hello, t: ToolsStatus): void {
    const copy = h("button", { class: "btn btn-quiet", type: "button" }, "Copiar diagnóstico");
    copy.addEventListener("click", async () => {
      const text = [`Baixaí helper ${hello.version} (protocolo ${hello.protocol}, ${hello.platform})`, `Extensão: ${chrome.runtime.id}`, `yt-dlp: ${t.ytdlp.version ?? "ausente"} (${t.ytdlp.source ?? "-"})`,
        `gallery-dl: ${t.gallerydl.version ?? "ausente"} (${t.gallerydl.source ?? "-"})`, `FFmpeg: ${t.ffmpeg.version ?? "ausente"}`, `JS runtime: ${t.js_runtime.name ? `${t.js_runtime.name} ${t.js_runtime.version}` : "ausente"}`, `Python: ${t.python.version}${t.python.frozen ? " (empacotado)" : ""}`].join("\n");
      try { await navigator.clipboard.writeText(text); announce("Diagnóstico copiado"); msg.className = "status status-ok"; msg.textContent = "Diagnóstico copiado (não contém links nem caminhos pessoais)."; } catch { msg.textContent = "Não foi possível copiar."; }
    });
    const recheck = h("button", { class: "btn", type: "button" }, icon("retry"), "Verificar de novo");
    recheck.addEventListener("click", () => void load(true));
    const updates = h("div", { class: "card" }, h("h3", { class: "card-title", text: "Atualização do yt-dlp" }),
      h("p", { class: "muted", text: "Plataformas mudam com frequência e o yt-dlp precisa acompanhar. Nada é baixado ou atualizado sem a sua ação: a verificação consulta o GitHub e a atualização baixa o binário oficial e confere o SHA-256 publicado." }));
    const result = h("p", { class: "status", role: "status", "aria-live": "polite" });
    const check = h("button", { class: "btn", type: "button", text: "Verificar atualização" });
    const apply = h("button", { class: "btn btn-primary", type: "button", hidden: true }, icon("download"), "Atualizar o yt-dlp");
    check.addEventListener("click", async () => {
      check.disabled = true; result.className = "status"; result.textContent = "Consultando o GitHub…";
      try {
        const r = await client.call<{ ytdlp: { current: string | null; latest: string; update_available: boolean } }>("tools_check_updates");
        result.textContent = r.ytdlp.update_available ? `Há uma versão nova: ${r.ytdlp.latest} (instalada: ${r.ytdlp.current ?? "?"}).` : `O yt-dlp já está na versão mais recente (${r.ytdlp.current}).`;
        apply.hidden = !r.ytdlp.update_available;
      } catch (e) { result.className = "status status-error"; result.textContent = errorText(e); } finally { check.disabled = false; }
    });
    apply.addEventListener("click", async () => {
      if (!confirm("Baixar o yt-dlp mais recente do GitHub (github.com/yt-dlp/yt-dlp) e instalá-lo para este aplicativo? O arquivo é verificado pelo SHA-256 oficial.")) return;
      apply.disabled = true; result.className = "status"; result.textContent = "Baixando e verificando…";
      try { const r = await client.call<{ version: string }>("tools_update_ytdlp"); result.className = "status status-ok"; result.textContent = `yt-dlp atualizado para ${r.version}.`; apply.hidden = true; void load(true); }
      catch (e) { result.className = "status status-error"; result.textContent = errorText(e); } finally { apply.disabled = false; }
    });
    updates.append(h("div", { class: "row" }, check, apply), result);

    body.replaceChildren(
      h("table", { class: "table" }, h("caption", { class: "sr-only", text: "Componentes instalados" }),
        h("thead", {}, h("tr", {}, h("th", { scope: "col", text: "Componente" }), h("th", { scope: "col", text: "Estado" }), h("th", { scope: "col", text: "Detalhes" }))),
        h("tbody", {},
          rowOf("Aplicativo local", badge(true, "Conectado", ""), `v${hello.version} · protocolo ${hello.protocol} · ${hello.platform}`),
          rowOf("yt-dlp (vídeo e áudio)", badge(t.ytdlp.ok, "Instalado", "Ausente"), t.ytdlp.ok ? `${t.ytdlp.version} · ${t.ytdlp.source}` : "Reinstale o aplicativo auxiliar"),
          rowOf("gallery-dl (imagens e galerias)", badge(t.gallerydl.ok, "Instalado", "Ausente"), t.gallerydl.ok ? `${t.gallerydl.version} · ${t.gallerydl.source}` : "Reinstale o aplicativo auxiliar"),
          rowOf("FFmpeg (MP3 e combinação)", badge(t.ffmpeg.ok, "Encontrado", "Não encontrado"), t.ffmpeg.ok ? (t.ffmpeg.version ?? "") : "Sem ele, MP3 e vídeos com faixas separadas não funcionam. Veja a aba Ajuda."),
          rowOf("Runtime JavaScript (YouTube)", badge(t.js_runtime.ok, "Encontrado", "Não encontrado"), t.js_runtime.ok ? `${t.js_runtime.name} ${t.js_runtime.version}` : "Instale Deno ou Node.js 22+ para suporte completo ao YouTube"),
          rowOf("Python", badge(true, "OK", ""), `${t.python.version}${t.python.frozen ? " · aplicativo empacotado" : ""}`),
          rowOf("Pasta de downloads", badge(true, "OK", ""), hello.download_dir))),
      h("div", { class: "row" }, recheck, copy), updates,
      h("p", { class: "muted small", text: "gallery-dl e FFmpeg são atualizados reinstalando o aplicativo auxiliar ou pelo gerenciador de pacotes do seu sistema." }));
  }
  void load();
}
