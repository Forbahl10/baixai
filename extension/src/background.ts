/** Service worker: mantém a ponte com o aplicativo local, o menu de contexto e o selo de atividade. */
import { MENU_PATTERNS, managerUrl } from "./links";
import { BridgeError, NativeBridge, type NativePort } from "./native";
import { ACTIVE_STATES, COMMANDS, type ApiError, type Job } from "./protocol";
import { UI_PORT, type UiMessage, type UiRequest } from "./ui-protocol";

const bridge = new NativeBridge((host) => chrome.runtime.connectNative(host) as unknown as NativePort, () => chrome.runtime.lastError?.message);
const jobs = new Map<string, Job>();
const uiPorts = new Set<chrome.runtime.Port>();
let idleTimer: ReturnType<typeof setTimeout> | undefined;
const IDLE_MS = 90_000;

const activeCount = () => [...jobs.values()].filter((j) => (ACTIVE_STATES as readonly string[]).includes(j.state)).length;

function broadcast(msg: UiMessage): void {
  for (const p of uiPorts) { try { p.postMessage(msg); } catch { /* porta fechada */ } }
}

function updateBadge(): void {
  const n = activeCount();
  void chrome.action.setBadgeText({ text: n ? String(n) : "" });
  if (n) void chrome.action.setBadgeBackgroundColor({ color: "#0b7a75" });
}

/** Sem páginas abertas e sem trabalhos ativos, libera o aplicativo local (o service worker pode dormir). */
function scheduleIdle(): void {
  clearTimeout(idleTimer);
  if (uiPorts.size === 0 && activeCount() === 0 && bridge.state.kind === "connected") {
    idleTimer = setTimeout(() => { if (uiPorts.size === 0 && activeCount() === 0) bridge.disconnect(); }, IDLE_MS);
  }
}

async function refreshJobs(): Promise<void> {
  const r = await bridge.call<{ jobs: Job[] }>("list_jobs", { limit: 200 });
  jobs.clear();
  r.jobs.forEach((j) => jobs.set(j.id, j));
  updateBadge();
  broadcast({ t: "jobs", jobs: r.jobs });
}

bridge.onState((state) => {
  broadcast({ t: "status", state });
  if (state.kind === "connected") void refreshJobs().catch(() => undefined);
  if (state.kind !== "connected") { jobs.clear(); updateBadge(); }
});
bridge.onEvent((event) => {
  if (event.event === "job") jobs.set(event.job.id, event.job);
  else if (event.event === "removed") jobs.delete(event.id);
  else if (event.event === "cleared") event.ids.forEach((i) => jobs.delete(i));
  updateBadge();
  broadcast({ t: "event", event });
  scheduleIdle();
});

function senderIsOurs(port: chrome.runtime.Port): boolean {
  return port.sender?.id === chrome.runtime.id && typeof port.sender.url === "string" && port.sender.url.startsWith(chrome.runtime.getURL(""));
}

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== UI_PORT || !senderIsOurs(port)) { port.disconnect(); return; }
  uiPorts.add(port);
  clearTimeout(idleTimer);
  port.postMessage({ t: "status", state: bridge.state } satisfies UiMessage);
  port.postMessage({ t: "jobs", jobs: [...jobs.values()] } satisfies UiMessage);
  port.onDisconnect.addListener(() => { uiPorts.delete(port); scheduleIdle(); });
  port.onMessage.addListener((raw: UiRequest) => {
    if (!raw || typeof raw !== "object") return;
    if (raw.t === "connect" || raw.t === "hello") { void bridge.connect().catch(() => undefined); return; }
    if (raw.t !== "call" || typeof raw.id !== "string" || !(COMMANDS as readonly string[]).includes(raw.cmd)) return;
    bridge.call(raw.cmd, raw.payload ?? {}).then(
      (data) => port.postMessage({ t: "result", id: raw.id, ok: true, data } satisfies UiMessage),
      (e: unknown) => {
        const error: ApiError = e instanceof BridgeError ? e.error : { code: "internal", message: "Erro inesperado na extensão." };
        port.postMessage({ t: "result", id: raw.id, ok: false, error } satisfies UiMessage);
      },
    );
  });
});

function createMenus(): void {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "baixai-link", title: "Analisar link com o Baixaí", contexts: ["link"], targetUrlPatterns: MENU_PATTERNS });
    chrome.contextMenus.create({ id: "baixai-page", title: "Analisar esta página com o Baixaí", contexts: ["page"], documentUrlPatterns: MENU_PATTERNS });
  });
}

chrome.runtime.onInstalled.addListener((details) => {
  createMenus();
  if (details.reason === "install") void chrome.tabs.create({ url: chrome.runtime.getURL("manager.html") + "#/ajuda" });
});
// Retoma a fila persistente ao abrir o navegador.
chrome.runtime.onStartup.addListener(() => { void bridge.connect().then(scheduleIdle).catch(() => undefined); });

chrome.contextMenus.onClicked.addListener((info) => {
  const link = info.menuItemId === "baixai-link" ? info.linkUrl : info.menuItemId === "baixai-page" ? info.pageUrl : undefined;
  if (link) void chrome.tabs.create({ url: managerUrl(chrome.runtime.getURL("manager.html"), link) });
});
