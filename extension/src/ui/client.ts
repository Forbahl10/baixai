/** Cliente das páginas para o service worker (porta de longa duração com reconexão). */
import type { BridgeState } from "../native";
import type { ApiError, Cmd, HostEvent, Job } from "../protocol";
import { UI_PORT, type UiMessage, type UiRequest } from "../ui-protocol";

export class CallError extends Error { constructor(public readonly error: ApiError) { super(error.message); } }

export class UiClient {
  private port: chrome.runtime.Port | null = null;
  private seq = 0;
  private pending = new Map<string, { resolve(v: unknown): void; reject(e: CallError): void }>();
  state: BridgeState = { kind: "connecting" };
  jobs = new Map<string, Job>();
  private stateCbs = new Set<(s: BridgeState) => void>();
  private jobCbs = new Set<() => void>();
  private eventCbs = new Set<(e: HostEvent) => void>();

  constructor() { this.open(); }

  private open(): void {
    const port = chrome.runtime.connect({ name: UI_PORT });
    this.port = port;
    port.onMessage.addListener((m: UiMessage) => this.handle(m));
    port.onDisconnect.addListener(() => {
      void chrome.runtime.lastError;
      this.port = null;
      for (const [, p] of this.pending) p.reject(new CallError({ code: "disconnected", message: "A extensão foi reiniciada. Tente de novo." }));
      this.pending.clear();
      setTimeout(() => this.open(), 500);
    });
    this.send({ t: "connect" });
  }
  private send(m: UiRequest): void { try { this.port?.postMessage(m); } catch { /* reconecta */ } }

  private handle(m: UiMessage): void {
    switch (m.t) {
      case "status": this.state = m.state; this.stateCbs.forEach((cb) => cb(m.state)); break;
      case "jobs": this.jobs = new Map(m.jobs.map((j) => [j.id, j])); this.jobCbs.forEach((cb) => cb()); break;
      case "event": {
        const e = m.event;
        if (e.event === "job") this.jobs.set(e.job.id, e.job);
        else if (e.event === "removed") this.jobs.delete(e.id);
        else if (e.event === "cleared") e.ids.forEach((i) => this.jobs.delete(i));
        this.eventCbs.forEach((cb) => cb(e));
        this.jobCbs.forEach((cb) => cb());
        break;
      }
      case "result": {
        const p = this.pending.get(m.id);
        if (!p) return;
        this.pending.delete(m.id);
        if (m.ok) p.resolve(m.data); else p.reject(new CallError(m.error));
      }
    }
  }

  call<T>(cmd: Cmd, payload: Record<string, unknown> = {}): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      if (!this.port) { reject(new CallError({ code: "disconnected", message: "Sem conexão com a extensão. Tente de novo." })); return; }
      const id = `u${++this.seq}`;
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
      this.send({ t: "call", id, cmd, payload });
    });
  }
  retryConnect(): void { this.state = { kind: "connecting" }; this.stateCbs.forEach((cb) => cb(this.state)); this.send({ t: "connect" }); }
  onState(cb: (s: BridgeState) => void): void { this.stateCbs.add(cb); cb(this.state); }
  onJobs(cb: () => void): void { this.jobCbs.add(cb); }
  onEvent(cb: (e: HostEvent) => void): void { this.eventCbs.add(cb); }
}

export function errorText(e: unknown): string {
  if (e instanceof CallError) return e.error.message;
  return e instanceof Error ? e.message : "Erro inesperado.";
}
