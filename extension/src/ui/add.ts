import { formatBytes, formatDuration } from "../format";
import { extractUrls } from "../links";
import type { Analysis, EnqueueResult, GalleryItem, Job, Mode, VideoFormat } from "../protocol";
import { announce, h, icon } from "./dom";
import { errorText, type UiClient } from "./client";

export interface AddOptions { compact: boolean; initialUrl?: string | null }
type Opts = Record<string, unknown>;

function field(label: string, control: HTMLElement, hint?: string): HTMLElement {
  const id = control.id || `f${Math.random().toString(36).slice(2, 8)}`;
  control.id = id;
  const wrap = h("div", { class: "field" }, h("label", { for: id, text: label }), control);
  if (hint) { const hid = `${id}-hint`; wrap.appendChild(h("p", { class: "hint muted", id: hid, text: hint })); control.setAttribute("aria-describedby", hid); }
  return wrap;
}
function select(opts: [string, string][], value: string): HTMLSelectElement {
  const s = h("select", { class: "input" });
  for (const [v, l] of opts) s.appendChild(h("option", { value: v, text: l, ...(v === value ? { selected: true } : {}) }));
  s.value = value;
  return s;
}
function radios(name: string, items: [string, string][], value: string, onChange: (v: string) => void): HTMLElement {
  const g = h("div", { class: "seg", role: "radiogroup", "aria-label": name });
  for (const [v, l] of items) {
    const id = `${name}-${v}`.replace(/\W/g, "_") + Math.random().toString(36).slice(2, 5);
    const inp = h("input", { type: "radio", name: `${name}${id.slice(-3)}`, id, value: v, ...(v === value ? { checked: true } : {}) });
    inp.addEventListener("change", () => onChange(v));
    g.append(inp, h("label", { for: id, text: l }));
  }
  // todos os rádios do grupo compartilham o mesmo name para navegação por setas
  const nm = `g${Math.random().toString(36).slice(2, 8)}`;
  g.querySelectorAll("input").forEach((i) => i.setAttribute("name", nm));
  return g;
}

export function mountAdd(root: HTMLElement, client: UiClient, opts: AddOptions): void {
  const input = h("textarea", { id: "url-input", class: "input url-input", rows: opts.compact ? 2 : 3, placeholder: "Cole aqui o link (ou vários, um por linha)", spellcheck: false, autocomplete: "off", autocapitalize: "off" });
  const analyzeBtn = h("button", { class: "btn btn-primary", type: "button" }, icon("link"), "Analisar");
  const row = h("div", { class: "row" });
  if (opts.compact) {
    const tabBtn = h("button", { class: "btn", type: "button", title: "Usa o endereço da aba atual (somente quando você clica)" }, "Usar aba atual");
    tabBtn.addEventListener("click", async () => {
      try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab?.url && /^https?:/i.test(tab.url)) { input.value = tab.url; void analyze(); }
        else setStatus("A aba atual não é uma página http(s) analisável.", "error");
      } catch { setStatus("Não foi possível ler a aba atual.", "error"); }
    });
    row.appendChild(tabBtn);
  }
  row.appendChild(analyzeBtn);
  const status = h("p", { class: "status", role: "status", "aria-live": "polite" });
  const result = h("div", { class: "result" });
  root.append(
    h("form", { class: "add-form", on: { submit: (e) => { e.preventDefault(); void analyze(); } } },
      h("label", { for: "url-input", class: "big-label", text: "Link do vídeo, áudio ou imagem" }), input, row),
    status, result);

  function setStatus(msg: string, kind: "info" | "error" | "ok" = "info"): void {
    status.className = `status status-${kind}`; status.textContent = msg; if (msg) announce(msg);
  }
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); void analyze(); } });
  input.addEventListener("paste", () => setTimeout(() => { const n = extractUrls(input.value).valid.length; if (n > 1) setStatus(`${n} links detectados. Clique em Analisar para adicioná-los juntos.`); }, 0));

  let busy = false;
  async function analyze(): Promise<void> {
    if (busy) return;
    const { valid, invalid, truncated } = extractUrls(input.value);
    result.replaceChildren();
    if (!valid.length) { setStatus(invalid.length ? "Esse texto não é um link http(s) válido." : "Cole um link para analisar.", "error"); input.focus(); return; }
    if (valid.length > 1) { renderBatch(valid, invalid, truncated); setStatus(""); return; }
    busy = true; analyzeBtn.disabled = true;
    setStatus("Analisando o link…");
    result.appendChild(h("div", { class: "skeleton", "aria-hidden": "true" }));
    try {
      const a = await client.call<Analysis>("analyze", { url: valid[0] });
      result.replaceChildren();
      setStatus("");
      renderAnalysis(a);
      announce(`Análise concluída: ${a.title ?? "conteúdo"}`);
    } catch (e) { result.replaceChildren(); setStatus(errorText(e), "error"); }
    finally { busy = false; analyzeBtn.disabled = false; }
  }

  // ------------------------------------------------------------------ resultado único
  function renderAnalysis(a: Analysis): void {
    const isPlaylist = a.kind === "playlist";
    let mode: Mode = a.modes[0] ?? "video";
    const optsBox = h("div", { class: "options" });
    const addBtn = h("button", { class: "btn btn-primary btn-lg", type: "button" }, icon("download"), "Adicionar à fila");
    const confirmBox = h("input", { type: "checkbox", id: "confirm-big" });
    const need = a.needs_confirmation;
    const getOpts: { fn: () => Opts } = { fn: () => ({}) };
    const refreshAdd = () => { addBtn.disabled = !a.modes.length || (need && !(confirmBox as HTMLInputElement).checked); };

    const thumb = a.thumbnail ? h("img", { class: "thumb", src: a.thumbnail, alt: "", loading: "lazy", decoding: "async", referrerpolicy: "no-referrer" }) : h("div", { class: "thumb thumb-empty", "aria-hidden": "true" }, icon("download"));
    const meta = [a.platform_label, a.author, a.duration ? formatDuration(a.duration) : "", a.size ? formatBytes(a.size) : ""].filter(Boolean).join(" · ");
    const card = h("section", { class: "card", "aria-label": "Prévia do conteúdo" },
      h("div", { class: "preview" }, thumb, h("div", { class: "preview-text" }, h("h2", { class: "card-title clamp", text: a.title ?? "Sem título", title: a.title ?? "" }), h("p", { class: "muted", text: meta }),
        isPlaylist || (a.entry_count ?? 0) > 1 ? h("p", { class: "badge", text: `${a.entry_count} ${isPlaylist ? "vídeos" : "arquivos"}${a.truncated ? " (ou mais)" : ""}` }) : null)));
    for (const w of a.warnings) card.appendChild(h("p", { class: "notice", role: "note" }, icon("alert"), w));

    const renderModes = () => {
      optsBox.replaceChildren();
      if (!a.modes.length) { optsBox.appendChild(h("p", { class: "notice" }, icon("alert"), "Não há opções de download disponíveis para este link.")); refreshAdd(); return; }
      if (a.modes.length > 1) optsBox.appendChild(radios("Tipo de download", a.modes.map((m) => [m, m === "video" ? "Vídeo" : m === "audio" ? "Áudio" : "Imagem"] as [string, string]), mode, (v) => { mode = v as Mode; renderModes(); }));
      if (mode === "video") getOpts.fn = videoControls(optsBox, a);
      else if (mode === "audio") getOpts.fn = audioControls(optsBox, a);
      else getOpts.fn = imageControls(optsBox, a);
      refreshAdd();
    };
    renderModes();
    card.appendChild(optsBox);

    if (need) {
      card.appendChild(h("div", { class: "confirm" }, confirmBox, h("label", { for: "confirm-big", text: `Confirmo adicionar ${a.entry_count}${a.truncated ? "+" : ""} itens de uma só vez.` })));
      confirmBox.addEventListener("change", refreshAdd);
    }
    refreshAdd();
    const feedback = h("div", { class: "feedback", role: "status", "aria-live": "polite" });
    addBtn.addEventListener("click", () => void submit(false));
    card.append(h("div", { class: "row end" }, addBtn), feedback);
    result.appendChild(card);

    async function submit(force: boolean): Promise<void> {
      addBtn.disabled = true; feedback.replaceChildren();
      const options = getOpts.fn();
      if (Array.isArray(options["items"]) && options["items"].length === 0) {
        feedback.replaceChildren(h("p", { class: "error", role: "alert", text: "Selecione ao menos um item da galeria." }));
        refreshAdd(); return;
      }
      try {
        if (isPlaylist) {
          const entries = (a.entries ?? []).map((e) => ({ url: e.url, meta: cleanMeta({ title: e.title, author: a.author, platform: a.platform }) }));
          const r = await client.call<{ results: ({ url: string; error?: { message: string }; duplicate?: string | null; job?: Job })[] }>("enqueue_batch", { entries, mode, options, force });
          const ok = r.results.filter((x) => !x.error && !x.duplicate).length;
          const dup = r.results.filter((x) => x.duplicate).length;
          const bad = r.results.filter((x) => x.error);
          feedback.replaceChildren(h("p", { class: "ok", text: `${ok} adicionado(s) à fila${dup ? `, ${dup} já existiam` : ""}${bad.length ? `, ${bad.length} com erro` : ""}.` }),
            ...bad.slice(0, 5).map((b) => h("p", { class: "muted", text: `${b.url}: ${b.error?.message}` })));
          announce(`${ok} itens adicionados à fila`);
        } else {
          const meta = cleanMeta({ title: a.title, author: a.author, thumbnail: a.thumbnail, platform: a.platform, count: a.entry_count });
          const r = await client.call<EnqueueResult>("enqueue", { url: a.url, mode, options: { ...options, engine: a.engine }, meta, force });
          if (r.duplicate === "active") feedback.replaceChildren(h("p", { class: "notice" }, icon("alert"), "Este download já está na fila."));
          else if (r.duplicate === "done") {
            const again = h("button", { class: "btn btn-sm", type: "button", text: "Baixar de novo" });
            again.addEventListener("click", () => void submit(true));
            feedback.replaceChildren(h("p", { class: "notice" }, icon("alert"), "Este conteúdo já foi baixado com as mesmas opções. ", again));
          } else { feedback.replaceChildren(h("p", { class: "ok" }, icon("check"), "Adicionado à fila.")); announce("Adicionado à fila"); }
        }
      } catch (e) { feedback.replaceChildren(h("p", { class: "error", role: "alert", text: errorText(e) })); }
      finally { refreshAdd(); }
    }
  }

  // ------------------------------------------------------------------ vários links
  function renderBatch(urls: string[], invalid: string[], truncated: boolean): void {
    let mode: Mode = "video";
    const optsBox = h("div", { class: "options" });
    const state = { fn: (): Opts => ({}) };
    const render = () => {
      optsBox.replaceChildren();
      if (mode === "video") {
        const hSel = select([["2160", "até 4K (2160p)"], ["1440", "até 1440p"], ["1080", "até 1080p"], ["720", "até 720p"], ["480", "até 480p"], ["360", "até 360p"]], "1080");
        const cSel = select([["mp4", "MP4 (mais compatível)"], ["original", "Formato original (sem converter)"]], "mp4");
        optsBox.append(field("Resolução máxima", hSel, "Cada link usa a melhor resolução disponível até o limite escolhido."), field("Formato", cSel));
        state.fn = () => ({ height: Number(hSel.value), container: cSel.value });
      } else if (mode === "audio") {
        const fSel = select([["mp3", "MP3"], ["original", "Áudio original (sem converter)"]], "mp3");
        const bSel = select([["128", "128 kbps"], ["192", "192 kbps"], ["256", "256 kbps"], ["320", "320 kbps"]], "192");
        optsBox.append(field("Formato", fSel), field("Qualidade do MP3", bSel, "Uma taxa de bits maior não melhora a qualidade da fonte; só aumenta o tamanho."));
        state.fn = () => (fSel.value === "mp3" ? { audio_format: "mp3", mp3_bitrate: Number(bSel.value) } : { audio_format: "original" });
      } else {
        const iSel = select([["original", "Original (recomendado)"], ["jpeg", "JPEG"], ["png", "PNG"]], "original");
        optsBox.append(field("Formato da imagem", iSel, "JPEG descarta transparência."));
        state.fn = () => ({ image_format: iSel.value });
      }
    };
    render();
    const go = h("button", { class: "btn btn-primary btn-lg", type: "button" }, icon("download"), `Adicionar ${urls.length} links à fila`);
    const out = h("div", { class: "feedback", role: "status", "aria-live": "polite" });
    go.addEventListener("click", async () => {
      go.disabled = true; out.replaceChildren();
      try {
        const r = await client.call<{ results: { url: string; error?: { message: string }; duplicate?: string | null }[] }>("enqueue_batch", { entries: urls.map((url) => ({ url })), mode, options: state.fn() });
        const ok = r.results.filter((x) => !x.error && !x.duplicate).length, dup = r.results.filter((x) => x.duplicate).length, bad = r.results.filter((x) => x.error);
        out.append(h("p", { class: "ok", text: `${ok} adicionado(s)${dup ? `, ${dup} já existiam` : ""}${bad.length ? `, ${bad.length} não puderam ser adicionados` : ""}.` }),
          ...bad.map((b) => h("p", { class: "muted", text: `${b.url} — ${b.error?.message}` })));
        announce(`${ok} links adicionados à fila`);
      } catch (e) { out.append(h("p", { class: "error", role: "alert", text: errorText(e) })); }
      finally { go.disabled = false; }
    });
    result.appendChild(h("section", { class: "card", "aria-label": "Vários links" },
      h("h2", { class: "card-title", text: `${urls.length} links prontos` }),
      h("p", { class: "muted", text: "Os links são adicionados com as mesmas opções. Cada um é analisado quando chega a vez dele na fila." }),
      truncated ? h("p", { class: "notice" }, icon("alert"), "Só os 200 primeiros links foram considerados.") : null,
      invalid.length ? h("p", { class: "notice" }, icon("alert"), `${invalid.length} item(ns) ignorado(s) por não serem links http(s) válidos.`) : null,
      radios("Tipo de download", [["video", "Vídeo"], ["audio", "Áudio"], ["image", "Imagem"]], mode, (v) => { mode = v as Mode; render(); }),
      optsBox, h("div", { class: "row end" }, go), out));
  }

  if (opts.initialUrl) { input.value = opts.initialUrl; void analyze(); }
}

function cleanMeta(m: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(m)) {
    if (typeof v === "string" && v) out[k] = v.slice(0, k === "thumbnail" ? 2048 : 400);
    else if (typeof v === "number" && Number.isInteger(v) && v >= 0 && v <= 100000) out[k] = v;
  }
  if (typeof out["thumbnail"] === "string" && (out["thumbnail"] as string).length >= 2048) delete out["thumbnail"];
  return out;
}

// ---------------------------------------------------------------------- controles por tipo
function videoControls(box: HTMLElement, a: Analysis): () => Opts {
  const formats: VideoFormat[] = a.video?.formats ?? [];
  const def = a.defaults.default_height;
  const pick = formats.find((f) => f.height !== null && f.height <= def) ?? formats[0];
  const sel = h("select", { class: "input" });
  formats.forEach((f, i) => sel.appendChild(h("option", { value: String(i), text: [f.label, f.detail && f.detail !== f.label ? f.detail : "", f.codec, f.size ? formatBytes(f.size) : ""].filter(Boolean).join(" · ") })));
  sel.value = String(Math.max(0, formats.indexOf(pick as VideoFormat)));
  const cont = select([["mp4", "MP4 (mais compatível)"], ["original", "Formato original (sem converter)"]], a.defaults.default_container);
  const info = h("div", { class: "hint-box" });
  const paint = () => {
    const f = formats[Number(sel.value)];
    info.replaceChildren();
    if (!f) return;
    if (f.needs_merge) info.appendChild(h("p", { class: "muted" }, icon("check"), f.note ?? "Vídeo e áudio serão combinados com o FFmpeg."));
    if (cont.value === "mp4" && f.compat_note) info.appendChild(h("p", { class: "notice" }, icon("alert"), f.compat_note));
    if (cont.value === "original") info.appendChild(h("p", { class: "muted", text: "Mantém o contêiner e os codecs da fonte, preservando a qualidade." }));
  };
  sel.addEventListener("change", paint); cont.addEventListener("change", paint); paint();
  box.append(field(a.kind === "playlist" ? "Resolução máxima" : "Resolução", sel, "Somente resoluções realmente disponíveis neste vídeo."), field("Formato", cont), info);
  return () => { const f = formats[Number(sel.value)]; return { ...(f?.height ? { height: f.height } : {}), container: cont.value }; };
}

function audioControls(box: HTMLElement, a: Analysis): () => Opts {
  const au = a.audio;
  const fmt = select([["mp3", "MP3"], ["original", "Áudio original (sem converter)"]], "mp3");
  const rates = au?.mp3_bitrates ?? [128, 192, 256, 320];
  const br = select(rates.map((r) => [String(r), `${r} kbps`] as [string, string]), String(rates.includes(a.defaults.default_mp3_bitrate) ? a.defaults.default_mp3_bitrate : 192));
  const brField = field("Qualidade do MP3", br, au?.note);
  fmt.addEventListener("change", () => { brField.hidden = fmt.value !== "mp3"; });
  box.append(field("Formato", fmt), brField,
    h("p", { class: "muted small", text: au?.can_embed_cover ? "Metadados e capa são preservados quando disponíveis e compatíveis com o formato." : "Este link não informa capa para incorporar." }));
  return () => (fmt.value === "mp3" ? { audio_format: "mp3", mp3_bitrate: Number(br.value) } : { audio_format: "original" });
}

function imageControls(box: HTMLElement, a: Analysis): () => Opts {
  const im = a.image;
  const items: GalleryItem[] = im?.items ?? [];
  const fmt = select([["original", "Original (recomendado)"], ["jpeg", "JPEG"], ["png", "PNG"]], a.defaults.default_image_format);
  const warn = h("p", { class: "notice", hidden: true }, icon("alert"), "JPEG não tem transparência: áreas transparentes ficam com fundo branco, e há compressão com perda.");
  fmt.addEventListener("change", () => { warn.hidden = fmt.value !== "jpeg"; }); warn.hidden = fmt.value !== "jpeg";
  box.append(field("Formato da imagem", fmt, im?.note), warn);
  const checks: HTMLInputElement[] = [];
  if (items.length > 1) {
    const count = h("span", { class: "muted" });
    const update = () => { count.textContent = `${checks.filter((c) => c.checked).length} de ${im?.total ?? items.length} selecionado(s)`; };
    const all = h("button", { class: "btn btn-sm btn-quiet", type: "button", text: "Selecionar tudo" });
    const none = h("button", { class: "btn btn-sm btn-quiet", type: "button", text: "Limpar seleção" });
    all.addEventListener("click", () => { checks.forEach((c) => (c.checked = true)); update(); });
    none.addEventListener("click", () => { checks.forEach((c) => (c.checked = false)); update(); });
    const grid = h("ul", { class: "gallery", "aria-label": "Itens da galeria" });
    for (const it of items) {
      const cb = h("input", { type: "checkbox", id: `it${it.index}`, checked: true, "data-index": it.index });
      cb.addEventListener("change", update);
      checks.push(cb);
      grid.appendChild(h("li", { class: "gitem" }, cb, h("label", { for: `it${it.index}` },
        it.kind === "image" ? h("img", { src: it.url, alt: "", loading: "lazy", decoding: "async", referrerpolicy: "no-referrer" }) : h("span", { class: "gfile", text: it.ext.toUpperCase() }),
        h("span", { class: "gname", text: `${it.index}. ${it.name}` }))));
    }
    box.append(h("div", { class: "row between" }, count, h("div", { class: "row" }, all, none)), grid);
    if ((im?.total ?? 0) > items.length) box.appendChild(h("p", { class: "muted small", text: `A lista mostra os primeiros ${items.length} de ${im?.total}. Ao baixar tudo, todos os itens são incluídos.` }));
    update();
  }
  return () => {
    const o: Opts = { image_format: fmt.value };
    if (checks.length && !checks.every((c) => c.checked)) o["items"] = checks.filter((c) => c.checked).map((c) => Number(c.dataset["index"]));
    return o;
  };
}
