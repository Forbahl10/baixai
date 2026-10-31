import assert from "node:assert/strict";
import { test } from "node:test";
import { BridgeError, classifyDisconnect, NativeBridge, type NativePort } from "../src/native";

class FakePort implements NativePort {
  sent: any[] = []; private msg: ((m: unknown) => void)[] = []; private dis: (() => void)[] = []; closed = false;
  onMessage = { addListener: (cb: (m: unknown) => void) => void this.msg.push(cb) };
  onDisconnect = { addListener: (cb: () => void) => void this.dis.push(cb) };
  constructor(private auto: (m: any, port: FakePort) => void = () => {}) {}
  postMessage(m: unknown) { this.sent.push(m); queueMicrotask(() => this.auto(m, this)); }
  disconnect() { this.closed = true; }
  emit(m: unknown) { this.msg.forEach((cb) => cb(m)); }
  drop() { this.dis.forEach((cb) => cb()); }
}
const hello = (p = 1) => ({ app: "Baixaí", version: "0.1.0", protocol: p, platform: "darwin", download_dir: "/x", tools: {}, settings: {}, active_jobs: 0 });
const answer = (m: any, port: FakePort) => port.emit({ id: m.id, ok: true, data: m.cmd === "hello" ? hello() : { echo: m.cmd, payload: m.payload } });

test("classifyDisconnect distingue as causas documentadas do Chrome", () => {
  assert.equal(classifyDisconnect("Specified native messaging host not found.").reason, "host_missing");
  assert.equal(classifyDisconnect("Access to the specified native messaging host is forbidden.").reason, "forbidden");
  assert.equal(classifyDisconnect("Native host has exited.").reason, "exited");
  assert.equal(classifyDisconnect(undefined).reason, "unknown");
});

test("conecta, valida o protocolo e correlaciona respostas por id", async () => {
  const port = new FakePort(answer);
  const b = new NativeBridge(() => port);
  const states: string[] = []; b.onState((s) => states.push(s.kind));
  const r = await b.call<{ echo: string }>("analyze", { url: "https://x.com/a" });
  assert.equal(r.echo, "analyze");
  assert.deepEqual(states, ["connecting", "connected"]);
  assert.equal(port.sent[0].cmd, "hello");
  const [x, y] = await Promise.all([b.call<any>("list_jobs"), b.call<any>("get_settings")]);
  assert.equal(x.echo, "list_jobs"); assert.equal(y.echo, "get_settings");
});

test("host ausente: estado de erro com instrução e rejeição clara", async () => {
  const port = new FakePort();
  const b = new NativeBridge(() => port, () => "Specified native messaging host not found.");
  const p = b.call("analyze", { url: "https://x.com/a" });
  queueMicrotask(() => port.drop());
  await assert.rejects(p, (e: BridgeError) => e.error.code === "disconnected");
  assert.equal(b.state.kind, "error");
  assert.equal(b.state.kind === "error" && b.state.reason, "host_missing");
});

test("connectNative lançando exceção também vira erro de estado", async () => {
  const b = new NativeBridge(() => { throw new Error("Specified native messaging host not found."); });
  await assert.rejects(b.connect(), (e: BridgeError) => e.error.code === "host_missing");
  assert.equal(b.state.kind, "error");
});

test("versão de protocolo incompatível é recusada", async () => {
  const port = new FakePort((m, p) => p.emit({ id: m.id, ok: true, data: hello(99) }));
  const b = new NativeBridge(() => port);
  await assert.rejects(b.connect(), (e: BridgeError) => e.error.code === "version");
  assert.ok(port.closed);
});

test("erros do host chegam como BridgeError tipado", async () => {
  const port = new FakePort((m, p) => (m.cmd === "hello" ? answer(m, p) : p.emit({ id: m.id, ok: false, error: { code: "invalid_scheme", message: "Somente http(s)." } })));
  const b = new NativeBridge(() => port);
  await assert.rejects(b.call("analyze", { url: "ftp://x" }), (e: BridgeError) => e.error.code === "invalid_scheme");
});

test("eventos e mensagens inválidas: válidos são entregues, inválidos descartados", async () => {
  const port = new FakePort(answer);
  const b = new NativeBridge(() => port);
  const evs: string[] = []; b.onEvent((e) => evs.push(e.event));
  await b.connect();
  port.emit({ event: "job", job: { id: "j", url: "u", state: "done", files: [] } });
  port.emit({ event: "job", job: { nope: true } }); port.emit("lixo"); port.emit({ id: "desconhecido", ok: true });
  assert.deepEqual(evs, ["job"]);
});

test("evento fatal (origem não autorizada) vira estado 'forbidden'", async () => {
  const port = new FakePort();
  const b = new NativeBridge(() => port);
  void b.connect().catch(() => undefined);
  port.emit({ event: "fatal", error: { code: "origin_not_allowed", message: "Esta extensão não está autorizada." } });
  port.drop();
  assert.equal(b.state.kind === "error" && b.state.reason, "forbidden");
});

test("timeout rejeita a chamada pendente", async () => {
  const port = new FakePort((m, p) => { if (m.cmd === "hello") answer(m, p); });
  const b = new NativeBridge(() => port);
  await b.connect();
  const orig = setTimeout; (globalThis as any).setTimeout = (fn: () => void) => orig(fn, 5);
  try { await assert.rejects(b.call("list_jobs"), (e: BridgeError) => e.error.code === "timeout"); } finally { (globalThis as any).setTimeout = orig; }
});
