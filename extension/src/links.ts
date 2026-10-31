/** Utilitários de links: extração de URLs coladas e reconhecimento de plataformas compatíveis. */

export const MAX_BATCH = 200;
export interface Extracted { valid: string[]; invalid: string[]; truncated: boolean }

/** Extrai links http/https de um texto (um por linha, separados por espaço ou vírgula). Remove duplicados. */
export function extractUrls(text: string): Extracted {
  const seen = new Set<string>();
  const valid: string[] = [];
  const invalid: string[] = [];
  for (const raw of text.split(/[\s,;]+/)) {
    const token = raw.trim().replace(/^[<("'[]+|[>)"'\].,]+$/g, "");
    if (!token) continue;
    let u: URL | null = null;
    try { u = new URL(token); } catch { /* inválido */ }
    if (!u || (u.protocol !== "http:" && u.protocol !== "https:") || u.username || u.password || !u.hostname.includes(".")) {
      invalid.push(token);
      continue;
    }
    u.hash = "";
    const norm = u.toString();
    if (!seen.has(norm)) { seen.add(norm); valid.push(norm); }
  }
  return { valid: valid.slice(0, MAX_BATCH), invalid, truncated: valid.length > MAX_BATCH };
}

const DOMAINS: Record<string, string[]> = {
  youtube: ["youtube.com", "youtu.be", "youtube-nocookie.com"],
  instagram: ["instagram.com"],
  tiktok: ["tiktok.com"],
  twitter: ["twitter.com", "x.com"],
  soundcloud: ["soundcloud.com"],
  spotify: ["open.spotify.com"],
};
export const PLATFORM_LABEL: Record<string, string> = { youtube: "YouTube", instagram: "Instagram", tiktok: "TikTok", twitter: "X (Twitter)", soundcloud: "SoundCloud", spotify: "Spotify", direct: "Link direto" };

export function platformOf(url: string): string | null {
  let host: string;
  try { host = new URL(url).hostname.toLowerCase(); } catch { return null; }
  for (const [id, domains] of Object.entries(DOMAINS)) {
    if (domains.some((d) => host === d || host.endsWith("." + d))) return id;
  }
  return null;
}

/** Padrões usados no menu de contexto (links). O aplicativo local faz a classificação definitiva. */
export const MENU_PATTERNS: string[] = [
  "*://*.youtube.com/*", "*://youtu.be/*", "*://*.instagram.com/*", "*://*.tiktok.com/*",
  "*://*.twitter.com/*", "*://x.com/*", "*://*.x.com/*", "*://soundcloud.com/*", "*://*.soundcloud.com/*",
  "*://open.spotify.com/*",
];

/** Monta a URL da página de gerenciamento que já abre analisando um link. */
export function managerUrl(base: string, link?: string): string {
  return link ? `${base}#/adicionar?url=${encodeURIComponent(link)}` : base;
}
export function readHashUrl(hash: string): string | null {
  const m = /^#\/adicionar\?url=(.+)$/.exec(hash);
  if (!m || !m[1]) return null;
  try { return decodeURIComponent(m[1]); } catch { return null; }
}
