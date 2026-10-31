import type { ApiError, JobState } from "./protocol";

export function formatBytes(n: number | null | undefined): string {
  if (!n || n <= 0) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v >= 100 || i === 0 ? Math.round(v) : v.toFixed(1).replace(".", ",")} ${units[i]}`;
}
export function formatDuration(sec: number | null | undefined): string {
  if (!sec || sec < 0) return "";
  const s = Math.round(sec), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const p = (x: number) => String(x).padStart(2, "0");
  return h ? `${h}:${p(m)}:${p(r)}` : `${m}:${p(r)}`;
}
export function formatSpeed(bps: number | null | undefined): string { return bps ? `${formatBytes(bps)}/s` : ""; }
export function formatEta(sec: number | null | undefined): string { return sec != null && sec >= 0 ? `faltam ${formatDuration(sec) || "0:00"}` : ""; }

export const STATE_LABEL: Record<JobState, string> = {
  waiting: "Aguardando", analyzing: "Analisando", downloading: "Baixando", converting: "Convertendo", done: "Concluído", cancelled: "Cancelado", failed: "Falhou",
};
export const MODE_LABEL = { video: "Vídeo", audio: "Áudio", image: "Imagem" } as const;

export function describeError(e: ApiError): string { return e.message; }
export function pct(p: number | null | undefined): number | null { return p == null ? null : Math.max(0, Math.min(100, Math.round(p * 100))); }
