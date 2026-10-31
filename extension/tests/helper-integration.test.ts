// Integração real: a ponte da extensão (src/native.ts) falando com o aplicativo local Python
// pelo mesmo enquadramento do Native Messaging (prefixo de 32 bits em ordem nativa).
import assert from "node:assert/strict";
import { type ChildProcess, spawn } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir, endianness } from "node:os";
import { join, resolve } from "node:path";
import { after, before, test } from "node:test";
import { NativeBridge, type NativePort } from "../src/native";
import type { Job } from "../src/protocol";

const root = resolve(process.cwd());
const python = process.env["BAIXAI_PYTHON"] ?? join(root, ".venv/bin/python");
const EXT_ID = "gipfhgbdolmibhecjiemjdodedbfmahg";
const LE = endianness() === "LE";

// PNG 1x1 válido (RGBA, transparente)
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", "base64");

class ProcPort implements NativePort {
  private msg: ((m: unknown) => void)[] = []; private dis: (() => void)[] = []; private buf = Buffer.alloc(0); readonly proc: ChildProcess;
  onMessage = { addListener: (cb: (m: unknown) => void) => void this.msg.push(cb) };
  onDisconnect = { addListener: (cb: () => void) => void this.dis.push(cb) };
  constructor(env: NodeJS.ProcessEnv) {
    this.proc = spawn(python, ["-I", "-m", "baixai_helper", `chrome-extension://${EXT_ID}/`], { env: { ...process.env, ...env }, stdio: ["pipe", "pipe", "ignore"] });
    this.proc.stdout!.on("data", (d: Buffer) => {
      this.buf = Buffer.concat([this.buf, d]);
      while (this.buf.length >= 4) {
        const n = LE ? this.buf.readUInt32LE(0) : this.buf.readUInt32BE(0);
        if (this.buf.length < 4 + n) break;
        const body = this.buf.subarray(4, 4 + n); this.buf = this.buf.subarray(4 + n);
        const m = JSON.parse(body.toString("utf8")); this.msg.forEach((cb) => cb(m));
      }
    });
    this.proc.on("exit", () => this.dis.forEach((cb) => cb()));
  }
  postMessage(m: unknown) {
    const body = Buffer.from(JSON.stringify(m), "utf8"); const h = Buffer.alloc(4);
    LE ? h.writeUInt32LE(body.length) : h.writeUInt32BE(body.length);
    this.proc.stdin!.write(Buffer.concat([h, body]));
  }
  disconnect() { this.proc.stdin!.end(); setTimeout(() => this.proc.kill(), 3000).unref(); }
}

const skip = !existsSync(python) && `Python do helper não encontrado em ${python}`;
const server = createServer((req, res) => {
  const head = req.method === "HEAD";
  res.writeHead(200, { "Content-Type": "image/png", "Content-Length": PNG.length }); res.end(head ? undefined : PNG);
});
let bridge: NativeBridge; let dl: string; let url: string;

before(async () => {
  if (skip) return;
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  url = `http://127.0.0.1:${(server.address() as any).port}/figura.png`;
  const data = mkdtempSync(join(tmpdir(), "baixai-ext-"));
  dl = join(data, "Downloads");
  bridge = new NativeBridge(() => new ProcPort({ BAIXAI_DATA_DIR: join(data, "app"), BAIXAI_ALLOWED_IDS: EXT_ID, BAIXAI_ALLOW_PRIVATE_NETWORK: "1" }));
});
after(() => { bridge?.disconnect(); server.close(); });

test("hello: detecta o aplicativo local e confere o protocolo", { skip }, async () => {
  const h = await bridge.connect();
  assert.equal(h.protocol, 1); assert.equal(bridge.state.kind, "connected");
  assert.ok("ytdlp" in h.tools && "ffmpeg" in h.tools);
});

test("comando inválido recebe erro estruturado e a conexão continua", { skip }, async () => {
  await assert.rejects(bridge.call("analyze", { url: 123 }), (e: any) => e.error.code === "invalid_payload");
  await assert.rejects(bridge.call("analyze", { url: "ftp://x.com/a" }), (e: any) => e.error.code === "invalid_scheme");
  assert.equal((await bridge.call<any>("get_settings")).settings.max_concurrent, 2);
});

test("fluxo: configurar pasta → analisar → enfileirar → eventos de progresso → arquivo no disco", { skip }, async () => {
  await bridge.call("set_settings", { settings: { download_dir: dl } });
  const a = await bridge.call<any>("analyze", { url });
  assert.deepEqual(a.modes, ["image"]);
  const seen: string[] = [];
  const done = new Promise<Job>((res) => bridge.onEvent((e) => { if (e.event === "job") { seen.push(e.job.state); if (e.job.state === "done") res(e.job); } }));
  const r = await bridge.call<any>("enqueue", { url, mode: "image", options: { image_format: "original", engine: "direct" }, meta: { title: "figura" } });
  assert.equal(r.duplicate, null);
  const job = await done;
  assert.ok(seen.includes("downloading"));
  const files = readdirSync(join(dl, "Link direto"));
  assert.equal(files.length, 1); assert.equal(job.files[0]!.name, files[0]);
  const again = await bridge.call<any>("enqueue", { url, mode: "image", options: { image_format: "original" } });
  assert.equal(again.duplicate, "done");
  const list = await bridge.call<{ jobs: Job[] }>("list_jobs");
  assert.equal(list.jobs[0]!.state, "done");
});
