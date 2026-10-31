import assert from "node:assert/strict";
import { test } from "node:test";
import { formatBytes, formatDuration, formatEta, pct } from "../src/format";
import { parseHostMessage } from "../src/protocol";

const job = { id: "a1", url: "https://x.com/a", state: "downloading", files: [], mode: "video" };

test("parseHostMessage aceita respostas, erros e eventos válidos", () => {
  assert.deepEqual(parseHostMessage({ id: "m1", ok: true, data: { a: 1 } }), { kind: "response", id: "m1", ok: true, data: { a: 1 } });
  const err = parseHostMessage({ id: "m2", ok: false, error: { code: "network", message: "falha", retryable: true } });
  assert.deepEqual(err, { kind: "response", id: "m2", ok: false, error: { code: "network", message: "falha", retryable: true } });
  assert.equal(parseHostMessage({ event: "job", job })?.kind, "event");
  assert.deepEqual(parseHostMessage({ event: "removed", id: "a1" }), { kind: "event", event: { event: "removed", id: "a1" } });
});

test("parseHostMessage descarta mensagens malformadas", () => {
  for (const bad of [null, 5, "x", [], {}, { event: "job", job: { id: 1 } }, { event: "job", job: { ...job, state: "voando" } }, { event: "desconhecido" }, { event: "removed" }, { ok: "sim" }]) {
    assert.equal(parseHostMessage(bad), null, JSON.stringify(bad));
  }
});

test("erro sem formato esperado vira bad_response (sem vazar objeto interno)", () => {
  const m = parseHostMessage({ id: "m", ok: false, error: { stack: "segredo" } });
  assert.ok(m && m.kind === "response" && !m.ok && m.error.code === "bad_response" && !JSON.stringify(m).includes("segredo"));
});

test("formatadores", () => {
  assert.equal(formatBytes(0), ""); assert.equal(formatBytes(1536), "1,5 KB"); assert.equal(formatBytes(15_469_474), "14,8 MB");
  assert.equal(formatDuration(217), "3:37"); assert.equal(formatDuration(3725), "1:02:05"); assert.equal(formatEta(65), "faltam 1:05");
  assert.equal(pct(null), null); assert.equal(pct(0.456), 46); assert.equal(pct(7), 100);
});
