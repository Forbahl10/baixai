// Compila os testes TypeScript da extensão com esbuild e roda com o test runner do Node.
import { build } from "esbuild";
import { readdirSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "extension/tests");
const out = join(root, "build/tests");
rmSync(out, { recursive: true, force: true });
const entries = readdirSync(src).filter((f) => f.endsWith(".test.ts")).map((f) => join(src, f));
await build({ entryPoints: entries, outdir: out, bundle: true, platform: "node", format: "esm", outExtension: { ".js": ".mjs" }, logLevel: "warning", target: "node22" });
const r = spawnSync(process.execPath, ["--test", ...readdirSync(out).filter((f) => f.endsWith(".mjs")).map((f) => join(out, f))], { stdio: "inherit", cwd: root });
process.exit(r.status ?? 1);
