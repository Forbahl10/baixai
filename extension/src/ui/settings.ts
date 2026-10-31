import type { Settings } from "../protocol";
import { announce, h, icon } from "./dom";
import { errorText, type UiClient } from "./client";

function row(label: string, control: HTMLElement, hint?: string): HTMLElement {
  const id = control.id || `s${Math.random().toString(36).slice(2, 8)}`;
  control.id = id;
  const w = h("div", { class: "field" }, h("label", { for: id, text: label }), control);
  if (hint) { w.appendChild(h("p", { class: "hint muted", id: `${id}-h`, text: hint })); control.setAttribute("aria-describedby", `${id}-h`); }
  return w;
}
const sel = (opts: [string, string][], v: string) => { const s = h("select", { class: "input" }); opts.forEach(([val, l]) => s.appendChild(h("option", { value: val, text: l }))); s.value = v; return s; };
const check = (id: string, label: string, v: boolean) => { const c = h("input", { type: "checkbox", id, checked: v }); return { c, el: h("div", { class: "check" }, c, h("label", { for: id, text: label })) }; };

export function mountSettings(root: HTMLElement, client: UiClient): void {
  const form = h("form", { class: "settings", novalidate: true });
  const msg = h("p", { class: "status", role: "status", "aria-live": "polite" });
  root.append(form, msg);
  let loaded = false;

  async function load(): Promise<void> {
    try {
      const { settings: s, download_dir } = await client.call<{ settings: Settings; download_dir: string }>("get_settings");
      render(s, download_dir); loaded = true; msg.textContent = "";
    } catch (e) { msg.className = "status status-error"; msg.textContent = `Configurações indisponíveis: ${errorText(e)}`; }
  }
  client.onState((st) => { if (st.kind === "connected" && !loaded) void load(); });

  function render(s: Settings, dir: string): void {
    const dirInput = h("input", { class: "input", type: "text", value: s.download_dir || dir, "aria-label": "Pasta de destino" });
    const choose = h("button", { class: "btn", type: "button" }, icon("folder"), "Escolher pasta…");
    choose.addEventListener("click", async () => {
      choose.disabled = true; msg.textContent = "Aguardando a escolha da pasta na janela do sistema…";
      try {
        const r = await client.call<{ chosen: boolean; download_dir?: string }>("choose_folder");
        if (r.chosen && r.download_dir) { dirInput.value = r.download_dir; msg.className = "status status-ok"; msg.textContent = "Pasta atualizada."; announce("Pasta de destino atualizada"); } else msg.textContent = "";
      } catch (e) { msg.className = "status status-error"; msg.textContent = errorText(e); } finally { choose.disabled = false; }
    });
    const byPlat = check("o-plat", "Organizar em pastas por plataforma", s.organize_by_platform);
    const byAuth = check("o-auth", "Organizar em subpastas por autor", s.organize_by_author);
    const conc = sel([1, 2, 3, 4, 5].map((n) => [String(n), `${n}`] as [string, string]), String(s.max_concurrent));
    const cont = sel([["mp4", "MP4 (mais compatível)"], ["original", "Formato original"]], s.default_container);
    const hei = sel([2160, 1440, 1080, 720, 480, 360].map((n) => [String(n), `até ${n}p`] as [string, string]), String(s.default_height));
    const br = sel([128, 192, 256, 320].map((n) => [String(n), `${n} kbps`] as [string, string]), String(s.default_mp3_bitrate));
    const img = sel([["original", "Original (recomendado)"], ["jpeg", "JPEG"], ["png", "PNG"]], s.default_image_format);
    const thr = h("input", { class: "input", type: "number", min: 1, max: 1000, value: String(s.playlist_confirm_threshold) });
    const ff = h("input", { class: "input", type: "text", value: s.ffmpeg_path, placeholder: "Automático (PATH e pastas comuns)" });
    const save = h("button", { class: "btn btn-primary", type: "submit" }, icon("check"), "Salvar configurações");

    form.replaceChildren(
      h("fieldset", {}, h("legend", { text: "Destino" }),
        row("Pasta de destino", h("div", { class: "row nowrap" }, dirInput, choose), "A pasta é escolhida e gravada pelo aplicativo local. Você também pode digitar um caminho absoluto."), byPlat.el, byAuth.el),
      h("fieldset", {}, h("legend", { text: "Fila" }), row("Downloads simultâneos", conc, "Valores altos podem acionar limites das plataformas."),
        row("Pedir confirmação a partir de (itens)", thr, "Playlists e galerias maiores que isso pedem confirmação antes de entrar na fila.")),
      h("fieldset", {}, h("legend", { text: "Preferências padrão" }), row("Vídeo: formato", cont), row("Vídeo: resolução máxima", hei), row("MP3: qualidade", br, "Uma taxa de bits maior não melhora a qualidade da fonte."), row("Imagens: formato", img)),
      h("details", { class: "advanced" }, h("summary", { text: "Avançado" }), row("Caminho do FFmpeg (opcional)", ff, "Deixe em branco para detectar automaticamente. O caminho deve apontar para um executável.")),
      h("div", { class: "row end" }, save));

    form.onsubmit = async (ev) => {
      ev.preventDefault(); save.disabled = true;
      try {
        const settings: Record<string, unknown> = {
          download_dir: dirInput.value.trim(), organize_by_platform: byPlat.c.checked, organize_by_author: byAuth.c.checked, max_concurrent: Number(conc.value),
          default_container: cont.value, default_height: Number(hei.value), default_mp3_bitrate: Number(br.value), default_image_format: img.value,
          playlist_confirm_threshold: Math.max(1, Math.min(1000, Number(thr.value) || 20)),
        };
        if (ff.value.trim() || s.ffmpeg_path) settings["ffmpeg_path"] = ff.value.trim();
        await client.call("set_settings", { settings });
        msg.className = "status status-ok"; msg.textContent = "Configurações salvas."; announce("Configurações salvas");
      } catch (e) { msg.className = "status status-error"; msg.textContent = errorText(e); } finally { save.disabled = false; }
    };
  }
}
