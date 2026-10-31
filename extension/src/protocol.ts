/** Tipos e validação defensiva das mensagens trocadas com o aplicativo local. */

export const HOST_NAME = "local.baixai.helper";
export const PROTOCOL_VERSION = 1;

export type Mode = "video" | "audio" | "image";
export type JobState = "waiting" | "analyzing" | "downloading" | "converting" | "done" | "cancelled" | "failed";
export const JOB_STATES: readonly JobState[] = ["waiting", "analyzing", "downloading", "converting", "done", "cancelled", "failed"];
export const ACTIVE_STATES: readonly JobState[] = ["waiting", "analyzing", "downloading", "converting"];

export interface ApiError { code: string; message: string; detail?: string; retryable?: boolean }

export interface Job {
  id: string; url: string; platform: string | null; engine: string; mode: Mode;
  options: Record<string, unknown>; meta: { title?: string; author?: string; thumbnail?: string; platform?: string; count?: number };
  state: JobState; stage: string | null; progress: number | null; speed: number | null; eta: number | null; detail: string | null;
  files: { name: string; path: string }[]; notes: string[]; error: ApiError | null; attempts: number; created_at: number; updated_at: number;
}

export interface VideoFormat {
  height: number | null; label: string; detail?: string | null; codec: string; mp4_compatible: boolean; needs_merge: boolean;
  size: number | null; note?: string | null; compat_note?: string | null; fps?: number | null;
}
export interface GalleryItem { index: number; url: string; name: string; ext: string; kind: "image" | "video" | "audio" | "file"; width: number | null; height: number | null }
export interface Analysis {
  url: string; platform: string; platform_label: string; engine: "ytdlp" | "gallerydl" | "direct" | "spotify"; kind: string; content_kind: string;
  title: string | null; author: string | null; thumbnail: string | null; duration?: number | null; size?: number;
  modes: Mode[]; warnings: string[]; needs_confirmation: boolean; entry_count?: number; truncated?: boolean; truncated_list?: boolean;
  entries?: { index: number; url: string; title: string | null; duration: number | null }[];
  video?: { formats: VideoFormat[] };
  audio?: { source_codec: string | null; source_abr: number | null; mp3_bitrates: number[]; can_embed_cover: boolean; note: string };
  image?: { items: GalleryItem[]; total: number; formats: ("original" | "jpeg" | "png")[]; note: string };
  defaults: { default_height: number; default_container: "mp4" | "original"; default_mp3_bitrate: number; default_image_format: "original" | "jpeg" | "png" };
}
export interface Settings {
  download_dir: string; organize_by_platform: boolean; organize_by_author: boolean; max_concurrent: number; default_height: number;
  default_container: "mp4" | "original"; default_mp3_bitrate: number; default_image_format: "original" | "jpeg" | "png";
  playlist_confirm_threshold: number; ffmpeg_path: string; ytdlp_path: string; gallerydl_path: string;
}
export interface EngineStatus { ok: boolean; version: string | null; source: string | null }
export interface ToolsStatus {
  ytdlp: EngineStatus; gallerydl: EngineStatus; ffmpeg: { ok: boolean; path: string | null; version: string | null };
  js_runtime: { ok: boolean; name: string | null; path: string | null; version: string | null }; python: { version: string; frozen: boolean };
}
export interface Hello {
  app: string; version: string; protocol: number; platform: string; download_dir: string; tools: ToolsStatus; settings: Settings; active_jobs: number;
}
export interface EnqueueResult { job: Job; duplicate: "active" | "done" | null }

export type Cmd =
  | "hello" | "analyze" | "enqueue" | "enqueue_batch" | "list_jobs" | "cancel" | "retry" | "remove" | "reveal" | "job_log" | "clear_history"
  | "get_settings" | "set_settings" | "choose_folder" | "tools_status" | "tools_check_updates" | "tools_update_ytdlp";
export const COMMANDS: readonly Cmd[] = [
  "hello", "analyze", "enqueue", "enqueue_batch", "list_jobs", "cancel", "retry", "remove", "reveal", "job_log", "clear_history",
  "get_settings", "set_settings", "choose_folder", "tools_status", "tools_check_updates", "tools_update_ytdlp",
];

export type HostEvent =
  | { event: "job"; job: Job } | { event: "removed"; id: string } | { event: "cleared"; ids: string[] }
  | { event: "fatal"; error: ApiError };
export type HostMessage =
  | { kind: "response"; id: string | null; ok: true; data: unknown }
  | { kind: "response"; id: string | null; ok: false; error: ApiError }
  | { kind: "event"; event: HostEvent };

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

function parseError(v: unknown): ApiError {
  if (isObj(v) && typeof v["code"] === "string" && typeof v["message"] === "string") {
    const e: ApiError = { code: v["code"], message: v["message"] };
    if (typeof v["detail"] === "string") e.detail = v["detail"];
    if (typeof v["retryable"] === "boolean") e.retryable = v["retryable"];
    return e;
  }
  return { code: "bad_response", message: "Resposta inesperada do aplicativo local." };
}

export function isJob(v: unknown): v is Job {
  return isObj(v) && typeof v["id"] === "string" && typeof v["url"] === "string" && typeof v["state"] === "string" &&
    (JOB_STATES as readonly string[]).includes(v["state"]) && Array.isArray(v["files"]);
}

/** Valida o formato de uma mensagem recebida do host. Retorna null se for inválida (é descartada). */
export function parseHostMessage(raw: unknown): HostMessage | null {
  if (!isObj(raw)) return null;
  if (typeof raw["event"] === "string") {
    switch (raw["event"]) {
      case "job": return isJob(raw["job"]) ? { kind: "event", event: { event: "job", job: raw["job"] } } : null;
      case "removed": return typeof raw["id"] === "string" ? { kind: "event", event: { event: "removed", id: raw["id"] } } : null;
      case "cleared": return Array.isArray(raw["ids"]) ? { kind: "event", event: { event: "cleared", ids: raw["ids"].filter((x): x is string => typeof x === "string") } } : null;
      case "fatal": return { kind: "event", event: { event: "fatal", error: parseError(raw["error"]) } };
      default: return null;
    }
  }
  if (typeof raw["ok"] === "boolean") {
    const id = typeof raw["id"] === "string" ? raw["id"] : null;
    return raw["ok"] ? { kind: "response", id, ok: true, data: raw["data"] } : { kind: "response", id, ok: false, error: parseError(raw["error"]) };
  }
  return null;
}
