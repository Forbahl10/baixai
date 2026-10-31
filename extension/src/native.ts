/** Ponte com o host Native Messaging: uma porta de longa duração, requisições com id e timeouts. */
import { type ApiError, type Cmd, type Hello, type HostEvent, HOST_NAME, PROTOCOL_VERSION, parseHostMessage } from "./protocol";

export interface NativePort {
  postMessage(msg: unknown): void;
  disconnect(): void;
  onMessage: { addListener(cb: (msg: unknown) => void): void };
  onDisconnect: { addListener(cb: () => void): void };
}
export type DisconnectReason = "host_missing" | "forbidden" | "exited" | "version" | "unknown";
export type BridgeState =
  | { kind: "idle" } | { kind: "connecting" } | { kind: "connected"; hello: Hello }
  | { kind: "error"; reason: DisconnectReason; message: string };

export class BridgeError extends Error {
  constructor(public readonly error: ApiError) { super(error.message); }
}

export const TIMEOUTS: Partial<Record<Cmd, number>> = { analyze: 150_000, choose_folder: 320_000, tools_update_ytdlp: 180_000, tools_check_updates: 60_000, hello: 10_000 };
const DEFAULT_TIMEOUT = 30_000;

export function classifyDisconnect(lastError: string | undefined): { reason: DisconnectReason; message: string } {
  const m = (lastError ?? "").toLowerCase();
  if (m.includes("not found")) return { reason: "host_missing", message: "O aplicativo auxiliar local não está instalado (ou não foi registrado para este navegador)." };
  if (m.includes("forbidden")) return { reason: "forbidden", message: "O aplicativo auxiliar não autoriza esta extensão. O ID da extensão precisa estar registrado na instalação." };
  if (m.includes("exited") || m.includes("host has exited")) return { reason: "exited", message: "O aplicativo auxiliar foi encerrado inesperadamente." };
  return { reason: "unknown", message: lastError ? `Falha de comunicação: ${lastError}` : "A conexão com o aplicativo auxiliar foi encerrada." };
}

interface Pending { resolve(v: unknown): void; reject(e: BridgeError): void; timer: ReturnType<typeof setTimeout> }

export class NativeBridge {
  private port: NativePort | null = null;
  private pending = new Map<string, Pending>();
  private seq = 0;
  private connecting: Promise<Hello> | null = null;
  private fatal: ApiError | null = null;
  state: BridgeState = { kind: "idle" };
  private stateListeners = new Set<(s: BridgeState) => void>();
  private eventListeners = new Set<(e: HostEvent) => void>();

  constructor(private readonly connectNative: (host: string) => NativePort, private readonly lastError: () => string | undefined = () => undefined) {}

  onState(cb: (s: BridgeState) => void): () => void { this.stateListeners.add(cb); return () => this.stateListeners.delete(cb); }
  onEvent(cb: (e: HostEvent) => void): () => void { this.eventListeners.add(cb); return () => this.eventListeners.delete(cb); }
  private setState(s: BridgeState): void { this.state = s; this.stateListeners.forEach((cb) => cb(s)); }

  /** Conecta (se preciso) e confirma a versão do protocolo com `hello`. */
  connect(): Promise<Hello> {
    if (this.state.kind === "connected" && this.port) return Promise.resolve(this.state.hello);
    if (this.connecting) return this.connecting;
    this.fatal = null;
    this.setState({ kind: "connecting" });
    let port: NativePort;
    try {
      port = this.connectNative(HOST_NAME);
    } catch (e) {
      const c = classifyDisconnect(e instanceof Error ? e.message : String(e));
      this.setState({ kind: "error", ...c });
      return Promise.reject(new BridgeError({ code: c.reason, message: c.message }));
    }
    this.port = port;
    port.onMessage.addListener((raw) => this.handle(raw));
    port.onDisconnect.addListener(() => this.handleDisconnect(port));
    this.connecting = this.rawCall<Hello>("hello", {}).then((hello) => {
      if (hello.protocol !== PROTOCOL_VERSION) {
        const message = `Versão incompatível do aplicativo local (protocolo ${hello.protocol}; esperado ${PROTOCOL_VERSION}). Atualize o aplicativo auxiliar.`;
        this.setState({ kind: "error", reason: "version", message });
        port.disconnect();
        throw new BridgeError({ code: "version", message });
      }
      this.setState({ kind: "connected", hello });
      return hello;
    }).finally(() => { this.connecting = null; });
    return this.connecting;
  }

  async call<T>(cmd: Cmd, payload: Record<string, unknown> = {}): Promise<T> {
    if (cmd !== "hello") await this.connect();
    return this.rawCall<T>(cmd, payload);
  }

  private rawCall<T>(cmd: Cmd, payload: Record<string, unknown>): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      if (!this.port) return reject(new BridgeError({ code: "not_connected", message: "Sem conexão com o aplicativo local." }));
      const id = `m${++this.seq}`;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new BridgeError({ code: "timeout", message: "O aplicativo local demorou demais para responder.", retryable: true }));
      }, TIMEOUTS[cmd] ?? DEFAULT_TIMEOUT);
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject, timer });
      try { this.port.postMessage({ id, cmd, payload }); }
      catch { clearTimeout(timer); this.pending.delete(id); reject(new BridgeError({ code: "not_connected", message: "Sem conexão com o aplicativo local." })); }
    });
  }

  private handle(raw: unknown): void {
    const msg = parseHostMessage(raw);
    if (!msg) return;
    if (msg.kind === "event") {
      if (msg.event.event === "fatal") {
        this.fatal = msg.event.error;
        this.setState({ kind: "error", reason: "forbidden", message: msg.event.error.message });
      }
      this.eventListeners.forEach((cb) => cb(msg.event));
      return;
    }
    const p = msg.id ? this.pending.get(msg.id) : undefined;
    if (!p || !msg.id) return;
    clearTimeout(p.timer);
    this.pending.delete(msg.id);
    if (msg.ok) p.resolve(msg.data); else p.reject(new BridgeError(msg.error));
  }

  private handleDisconnect(port: NativePort): void {
    if (this.port !== port) return;
    const err = this.lastError();
    this.port = null;
    if (!this.fatal) {
      const c = classifyDisconnect(err);
      this.setState({ kind: "error", ...c });
    }
    const message = this.state.kind === "error" ? this.state.message : "A conexão com o aplicativo auxiliar foi encerrada.";
    for (const [id, p] of this.pending) { clearTimeout(p.timer); p.reject(new BridgeError({ code: "disconnected", message, retryable: true })); this.pending.delete(id); }
  }

  disconnect(): void { this.port?.disconnect(); this.port = null; this.setState({ kind: "idle" }); }
}
