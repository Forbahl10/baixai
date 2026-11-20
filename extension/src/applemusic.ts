/** Lê apenas título, artista, duração e link das faixas na aba atual do Apple Music. */
export interface AppleTrack { url: string; title: string; artist: string; duration: number }
export interface ApplePage { title: string; tracks: AppleTrack[] }

export function isApplePlaylist(url: string): boolean {
  try {
    const u = new URL(url);
    return u.hostname === "music.apple.com" && /^\/(?:[a-z]{2}\/)?(?:library\/)?playlist\/[A-Za-z0-9.]+\/?$/.test(u.pathname);
  } catch { return false; }
}

export function sameApplePlaylist(a: string, b: string): boolean {
  if (!isApplePlaylist(a) || !isApplePlaylist(b)) return false;
  return new URL(a).pathname.split("/").filter(Boolean).at(-1) === new URL(b).pathname.split("/").filter(Boolean).at(-1);
}

/** A função executada na aba é autocontida; não acessa cookies, tokens nem mídia. */
function readAppleMusicPage(): ApplePage & { truncated: boolean; incomplete: boolean } {
  const title = document.querySelector("h1")?.textContent?.trim() ?? "";
  const tracks: AppleTrack[] = [];
  let incomplete = false;
  for (const row of document.querySelectorAll("tr, [role='row']")) {
    const song = row.querySelector<HTMLAnchorElement>("a[href*='/song/']");
    if (!song) continue;
    const name = song.textContent?.trim() ?? "";
    const artists = [...row.querySelectorAll<HTMLAnchorElement>("a[href*='/artist/']")]
      .map((a) => a.textContent?.trim() ?? "").filter(Boolean);
    const artist = [...new Set(artists)].join(", ");
    const durationText = (row as HTMLElement).innerText.match(/\b\d{1,2}:[0-5]\d\b/g)?.at(-1);
    if (!name || !artist || !durationText) { incomplete = true; continue; }
    const [minutes, seconds] = durationText.split(":").map(Number);
    const duration = (minutes ?? 0) * 60 + (seconds ?? 0);
    const url = new URL(song.href, location.href);
    if (url.hostname !== "music.apple.com" || !/^\/(?:[a-z]{2}\/)?song\/[^/]+\/\d+\/?$/.test(url.pathname)) { incomplete = true; continue; }
    if (duration > 0) tracks.push({ url: url.toString(), title: name, artist, duration });
  }
  const countText = document.body.innerText.match(/\b(\d{1,4})\s+(?:músicas|songs)\b/i);
  if (countText && Number(countText[1]) > tracks.length) incomplete = true;
  return { title, tracks: tracks.slice(0, 200), truncated: tracks.length > 200, incomplete };
}

export async function captureAppleMusic(tabId: number): Promise<ApplePage> {
  const [result] = await chrome.scripting.executeScript({ target: { tabId }, func: readAppleMusicPage });
  const page = result?.result;
  if (!page?.title || !page.tracks.length) throw new Error("Não encontrei faixas nesta aba. Aguarde a playlist carregar e tente novamente.");
  if (page.truncated) throw new Error("Esta playlist tem mais de 200 faixas. O Baixaí ainda não consegue importá-la completa.");
  if (page.incomplete) throw new Error("Não consegui ler todas as faixas desta playlist. Aguarde a página carregar e tente novamente.");
  return { title: page.title, tracks: page.tracks };
}
