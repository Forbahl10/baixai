import { readHashUrl } from "./links";
import { mountAdd } from "./ui/add";
import { UiClient } from "./ui/client";
import { mountInstallBanner, mountStatusChip } from "./ui/connection";
import { mountDiagnostics } from "./ui/diagnostics";
import { $ } from "./ui/dom";
import { mountHelp } from "./ui/help";
import { mountJobs } from "./ui/jobs";
import { mountSettings } from "./ui/settings";
import { initTheme, themeToggle } from "./ui/theme";

initTheme();
const client = new UiClient();
mountStatusChip($("#chip"), client);
$("#theme").appendChild(themeToggle());
mountInstallBanner($("#banner"), client, { compact: false });

const ROUTES = ["adicionar", "downloads", "configuracoes", "diagnostico", "ajuda"] as const;
type Route = (typeof ROUTES)[number];
const mounted = new Set<Route>();
const initialLink = readHashUrl(location.hash);

function mount(route: Route): void {
  if (mounted.has(route)) return;
  mounted.add(route);
  const root = $(`#view-${route}`);
  if (route === "adicionar") mountAdd(root, client, { compact: false, initialUrl: initialLink });
  else if (route === "downloads") mountJobs(root, client, { toolbar: true, emptyText: "Nenhum download ainda. Cole um link na aba Adicionar." });
  else if (route === "configuracoes") mountSettings(root, client);
  else if (route === "diagnostico") mountDiagnostics(root, client);
  else mountHelp(root);
}

function currentRoute(): Route {
  const m = /^#\/([a-z]+)/.exec(location.hash);
  return (ROUTES as readonly string[]).includes(m?.[1] ?? "") ? (m![1] as Route) : "adicionar";
}
function show(): void {
  const r = currentRoute();
  mount(r);
  for (const name of ROUTES) {
    $(`#view-${name}`).hidden = name !== r;
    const link = $(`#nav-${name}`);
    if (name === r) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  }
  const title = $(`#nav-${r}`).textContent ?? "";
  document.title = `${title} · Baixaí`;
}
addEventListener("hashchange", show);
show();
const count = $("#nav-downloads-count");
client.onJobs(() => {
  const n = [...client.jobs.values()].filter((j) => ["waiting", "analyzing", "downloading", "converting"].includes(j.state)).length;
  count.textContent = n ? String(n) : ""; count.hidden = !n;
  count.setAttribute("aria-label", `${n} em andamento`);
});
