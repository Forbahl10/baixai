import { formatEta, formatSpeed, MODE_LABEL, pct, STATE_LABEL } from "../format";
import { PLATFORM_LABEL } from "../links";
import { ACTIVE_STATES, type Job } from "../protocol";
import { announce, h, icon } from "./dom";
import { errorText, type UiClient } from "./client";

const isActive = (j: Job) => (ACTIVE_STATES as readonly string[]).includes(j.state);

class Row {
  readonly el: HTMLLIElement;
  private title = h("p", { class: "job-title" });
  private meta = h("p", { class: "job-meta muted" });
  private chip = h("span", { class: "state" });
  private bar = h("div", { class: "bar", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": 100 }, h("div", { class: "bar-fill" }));
  private info = h("p", { class: "job-info muted" });
  private notes = h("ul", { class: "job-notes" });
  private err = h("p", { class: "job-error", role: "alert" });
  private actions = h("div", { class: "row job-actions" });
  private log = h("pre", { class: "job-log", hidden: true, tabindex: 0, "aria-label": "Registro do download" });
  private lastActionsKey = "";
  private lastState = "";

  constructor(private readonly client: UiClient, private job: Job) {
    this.el = h("li", { class: "job", "data-id": job.id },
      h("div", { class: "job-head" }, h("div", { class: "job-main" }, this.title, this.meta), this.chip),
      this.bar, this.info, this.notes, this.err, this.actions, this.log);
    this.update(job);
  }

  update(job: Job): void {
    this.job = job;
    const t = job.meta.title || job.files[0]?.name || job.url;
    this.title.textContent = t; this.title.title = job.url;
    const parts = [PLATFORM_LABEL[job.platform ?? ""] ?? job.platform ?? "", MODE_LABEL[job.mode], optionSummary(job)].filter(Boolean);
    this.meta.textContent = parts.join(" · ");
    this.chip.textContent = STATE_LABEL[job.state];
    this.chip.className = `state state-${job.state}`;
    const p = pct(job.progress);
    const active = job.state === "downloading" || job.state === "converting";
    this.bar.hidden = !(active || job.state === "analyzing");
    this.bar.classList.toggle("indeterminate", active && p === null);
    if (p !== null) this.bar.setAttribute("aria-valuenow", String(p)); else this.bar.removeAttribute("aria-valuenow");
    this.bar.setAttribute("aria-label", `${t}: ${STATE_LABEL[job.state]}${p !== null ? ` ${p}%` : ""}`);
    (this.bar.firstElementChild as HTMLElement).style.width = p === null ? "" : `${p}%`;
    this.info.textContent = [p !== null && active ? `${p}%` : "", formatSpeed(job.speed), formatEta(job.eta), job.detail ?? ""].filter(Boolean).join(" · ");
    this.info.hidden = !this.info.textContent;
    this.notes.replaceChildren(...job.notes.map((n) => h("li", { text: n })));
    this.notes.hidden = job.notes.length === 0;
    this.err.hidden = !job.error;
    this.err.textContent = job.error ? job.error.message : "";
    if (job.error?.detail) this.err.appendChild(h("small", { class: "muted", text: ` (${job.error.detail})` }));
    if (job.state !== this.lastState) { if (job.state === "done" || job.state === "failed" || job.state === "cancelled") announce(`${t}: ${STATE_LABEL[job.state]}`); this.lastState = job.state; }
    this.renderActions();
  }

  private btn(label: string, ic: Parameters<typeof icon>[0], fn: () => Promise<unknown> | void, quiet = true): HTMLButtonElement {
    const b = h("button", { class: `btn btn-sm${quiet ? " btn-quiet" : ""}`, type: "button" }, icon(ic), label);
    b.addEventListener("click", async () => {
      b.disabled = true;
      try { await fn(); } catch (e) { this.err.hidden = false; this.err.textContent = errorText(e); } finally { b.disabled = false; }
    });
    return b;
  }

  private renderActions(): void {
    const key = `${this.job.state}:${this.job.files.length}:${this.log.hidden}`;
    if (key === this.lastActionsKey) return;
    this.lastActionsKey = key;
    const id = this.job.id, c = this.client, j = this.job;
    const a: HTMLElement[] = [];
    if (isActive(j)) a.push(this.btn("Cancelar", "x", () => c.call("cancel", { id })));
    if (j.state === "failed" || j.state === "cancelled") a.push(this.btn("Tentar de novo", "retry", () => c.call("retry", { id }), false));
    if (j.state === "done") a.push(this.btn("Mostrar na pasta", "folder", () => c.call("reveal", { id }), false));
    a.push(this.btn(this.log.hidden ? "Ver registro" : "Ocultar registro", "logs", async () => {
      if (this.log.hidden) {
        const r = await c.call<{ lines: string[] }>("job_log", { id });
        this.log.textContent = r.lines.length ? r.lines.join("\n") : "Sem registros.";
      }
      this.log.hidden = !this.log.hidden; this.renderActions();
    }));
    if (!isActive(j)) a.push(this.btn("Remover", "trash", () => c.call("remove", { id })));
    this.actions.replaceChildren(...a);
  }
}

function optionSummary(j: Job): string {
  const o = j.options;
  if (j.mode === "video") return [o["height"] ? `até ${o["height"]}p` : "melhor qualidade", o["container"] === "original" ? "formato original" : "MP4"].join(", ");
  if (j.mode === "audio") return o["audio_format"] === "original" ? "áudio original" : `MP3 ${o["mp3_bitrate"] ?? 192} kbps`;
  const items = o["items"] as number[] | undefined;
  return [o["image_format"] === "original" ? "arquivo original" : String(o["image_format"]).toUpperCase(), items ? `${items.length} item(ns)` : ""].filter(Boolean).join(", ");
}

export function mountJobs(root: HTMLElement, client: UiClient, opts: { limit?: number; emptyText?: string; toolbar?: boolean } = {}): void {
  const list = h("ul", { class: "jobs", "aria-label": "Lista de downloads" });
  const empty = h("p", { class: "empty muted", text: opts.emptyText ?? "Nenhum download ainda." });
  if (opts.toolbar) {
    const clearBtn = h("button", { class: "btn btn-quiet btn-sm", type: "button" }, icon("trash"), "Limpar histórico");
    clearBtn.addEventListener("click", async () => {
      if (!confirm("Remover da lista os downloads concluídos, cancelados e com falha? Os arquivos baixados não serão apagados.")) return;
      try { const r = await client.call<{ removed: number }>("clear_history"); announce(`${r.removed} item(ns) removido(s) do histórico`); } catch (e) { announce(errorText(e)); }
    });
    root.appendChild(h("div", { class: "row toolbar" }, h("span", { class: "muted", text: "Downloads sobrevivem ao reinício do navegador." }), clearBtn));
  }
  root.append(list, empty);
  const rows = new Map<string, Row>();
  let queued = false;
  const sync = () => {
    queued = false;
    let jobs = [...client.jobs.values()].sort((a, b) => b.created_at - a.created_at);
    if (opts.limit) jobs = jobs.slice(0, opts.limit);
    const ids = new Set(jobs.map((j) => j.id));
    for (const [id, r] of rows) if (!ids.has(id)) { r.el.remove(); rows.delete(id); }
    jobs.forEach((j, i) => {
      let r = rows.get(j.id);
      if (!r) { r = new Row(client, j); rows.set(j.id, r); } else r.update(j);
      if (list.children[i] !== r.el) list.insertBefore(r.el, list.children[i] ?? null);
    });
    empty.hidden = jobs.length > 0;
  };
  client.onJobs(() => { if (!queued) { queued = true; requestAnimationFrame(sync); } });
  sync();
}
