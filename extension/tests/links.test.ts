import assert from "node:assert/strict";
import { test } from "node:test";
import { extractUrls, managerUrl, MAX_BATCH, platformOf, readHashUrl } from "../src/links";

test("extractUrls: vários formatos, dedupe e descarte de inválidos", () => {
  const r = extractUrls(`
    https://www.youtube.com/watch?v=abc#t=10
    (https://youtu.be/xyz), https://www.youtube.com/watch?v=abc
    ftp://x.com/a javascript:alert(1) texto-solto http://localhost relativo/caminho
    https://user:senha@example.com/x
  `);
  assert.deepEqual(r.valid, ["https://www.youtube.com/watch?v=abc", "https://youtu.be/xyz"]);
  assert.ok(r.invalid.includes("ftp://x.com/a") && r.invalid.some((x) => x.startsWith("javascript:")) && r.invalid.includes("http://localhost"));
  assert.ok(r.invalid.some((x) => x.includes("senha")));
});

test("extractUrls: limite de lote", () => {
  const text = Array.from({ length: MAX_BATCH + 5 }, (_, i) => `https://example.com/v/${i}`).join("\n");
  const r = extractUrls(text);
  assert.equal(r.valid.length, MAX_BATCH);
  assert.equal(r.truncated, true);
});

test("platformOf reconhece só domínios reais", () => {
  assert.equal(platformOf("https://music.youtube.com/watch?v=1"), "youtube");
  assert.equal(platformOf("https://x.com/a/status/1"), "twitter");
  assert.equal(platformOf("https://vm.tiktok.com/abc"), "tiktok");
  assert.equal(platformOf("https://evilyoutube.com/watch"), null);
  assert.equal(platformOf("https://youtube.com.evil.io/watch"), null);
  assert.equal(platformOf("não é url"), null);
});

test("managerUrl / readHashUrl fazem ida e volta", () => {
  const link = "https://www.youtube.com/watch?v=abc&list=PL1";
  const u = managerUrl("chrome-extension://id/manager.html", link);
  assert.equal(readHashUrl(new URL(u).hash), link);
  assert.equal(readHashUrl("#/downloads"), null);
  assert.equal(readHashUrl("#/adicionar?url=%E0%A4%A"), null);
});
