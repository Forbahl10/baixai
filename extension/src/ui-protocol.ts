/** Mensagens entre as páginas da extensão (popup/gerenciador) e o service worker. */
import type { BridgeState } from "./native";
import type { ApiError, Cmd, HostEvent, Job } from "./protocol";

export const UI_PORT = "baixai-ui";
export type UiRequest = { t: "call"; id: string; cmd: Cmd; payload?: Record<string, unknown> } | { t: "connect" } | { t: "hello" };
export type UiMessage =
  | { t: "result"; id: string; ok: true; data: unknown }
  | { t: "result"; id: string; ok: false; error: ApiError }
  | { t: "status"; state: BridgeState }
  | { t: "event"; event: HostEvent }
  | { t: "jobs"; jobs: Job[] };
