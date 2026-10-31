import { mountAdd } from "./ui/add";
import { UiClient } from "./ui/client";
import { mountInstallBanner, mountStatusChip } from "./ui/connection";
import { $ } from "./ui/dom";
import { mountJobs } from "./ui/jobs";
import { initTheme, themeToggle } from "./ui/theme";

initTheme();
const client = new UiClient();
mountStatusChip($("#chip"), client);
$("#theme").appendChild(themeToggle());
$("#open-manager").addEventListener("click", () => { void chrome.tabs.create({ url: chrome.runtime.getURL("manager.html") }); window.close(); });
mountInstallBanner($("#banner"), client, { compact: true });
mountAdd($("#add"), client, { compact: true });
mountJobs($("#jobs"), client, { limit: 4, emptyText: "Seus downloads aparecem aqui." });
