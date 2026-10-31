// Gera a extensão: bundle TypeScript (esbuild), manifest e pacotes.
//   node scripts/build-extension.mjs            -> dist/extension-unpacked (dev, com "key") e dist/baixai-extension-<versão>.zip (loja, sem "key")
import { build } from "esbuild";
import { createHash, generateKeyPairSync } from "node:crypto";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync, readdirSync, statSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ext = join(root, "extension");
const dist = join(root, "dist");
const version = JSON.parse(readFileSync(join(root, "package.json"), "utf8")).version;

// Chave pública de desenvolvimento: fixa o ID da extensão carregada descompactada.
// Só a chave pública é guardada; a privada é descartada (não é necessária e não deve ser versionada).
const keyFile = join(ext, "dev-public-key.txt");
if (!existsSync(keyFile)) {
  const { publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  writeFileSync(keyFile, publicKey.export({ type: "spki", format: "der" }).toString("base64") + "\n");
}
const pubB64 = readFileSync(keyFile, "utf8").trim();
const devId = [...createHash("sha256").update(Buffer.from(pubB64, "base64")).digest("hex").slice(0, 32)]
  .map((c) => String.fromCharCode("a".charCodeAt(0) + parseInt(c, 16))).join("");

async function assemble(outDir, { withKey }) {
  rmSync(outDir, { recursive: true, force: true });
  mkdirSync(outDir, { recursive: true });
  await build({
    entryPoints: { background: join(ext, "src/background.ts"), popup: join(ext, "src/popup.ts"), manager: join(ext, "src/manager.ts") },
    outdir: outDir, bundle: true, format: "iife", target: "chrome116", platform: "browser", sourcemap: false, minify: false, legalComments: "none", logLevel: "warning",
  });
  cpSync(join(ext, "public"), outDir, { recursive: true });
  const manifest = JSON.parse(readFileSync(join(ext, "manifest.template.json"), "utf8").replace("__VERSION__", version));
  if (withKey) manifest.key = pubB64;
  writeFileSync(join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
}

mkdirSync(dist, { recursive: true });
const unpacked = join(dist, "extension-unpacked");
await assemble(unpacked, { withKey: true });
writeFileSync(join(dist, "extension-dev-id.txt"), devId + "\n");
writeFileSync(join(ext, "dev-extension-id.txt"), devId + "\n"); // versionado: o empacotador do helper lê daqui

const store = join(root, "build", "extension-store");
await assemble(store, { withKey: false });
const zip = join(dist, `baixai-extension-${version}.zip`);
rmSync(zip, { force: true });
execFileSync("zip", ["-r", "-X", "-q", zip, "."], { cwd: store });
// Pacote "manual": mesma extensão com a chave pública de desenvolvimento => o ID é sempre o mesmo (DEFAULT_EXTENSION_IDS do instalador).
const manualDir = join(root, "build", "extension-manual");
await assemble(manualDir, { withKey: true });
const manualZip = join(dist, `baixai-extension-${version}-manual.zip`);
rmSync(manualZip, { force: true });
execFileSync("zip", ["-r", "-X", "-q", manualZip, "."], { cwd: manualDir });
console.log(`ZIP para instalação manual (ID fixo ${devId}): ${manualZip}`);
const size = statSync(zip).size;
console.log(`Extensão (dev, descompactada): ${unpacked}`);
console.log(`ID de desenvolvimento: ${devId}`);
console.log(`ZIP para a loja (sem "key"): ${zip} (${(size / 1024).toFixed(1)} KB)`);
console.log("Arquivos:", readdirSync(store).join(", "));
