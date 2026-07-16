import { api, apiUrl } from "../api";
import { h, clear, qs } from "../dom";
import { fmtDateTime } from "../format";
import { can, requireSession } from "../session";
import type { AuditEntry } from "../types";

const PAGE_SIZE = 50;
let offset = 0;
let total = 0;

const STATUS_BADGE: Record<string, string> = {
  success: "badge-ok",
  warning: "badge-warn",
  error: "badge-err",
};

function filters(): URLSearchParams {
  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  const action = qs<HTMLSelectElement>("#f-action").value;
  const status = qs<HTMLSelectElement>("#f-status").value;
  const actor = qs<HTMLInputElement>("#f-actor").value.trim();
  const target = qs<HTMLInputElement>("#f-target").value.trim();
  if (action) params.set("action", action);
  if (status) params.set("status", status);
  if (actor) params.set("actor", actor);
  if (target) params.set("target", target);
  return params;
}

async function load() {
  const response = await api.get<{ entries: AuditEntry[]; total: number; actions: string[] }>(
    `/api/logs?${filters()}`,
  );
  total = response.total;

  const actionSelect = qs<HTMLSelectElement>("#f-action");
  if (actionSelect.options.length <= 1) {
    for (const action of response.actions) {
      actionSelect.append(h("option", { value: action }, action));
    }
  }

  const tableRoot = qs<HTMLElement>("#log-table");
  clear(tableRoot);
  if (!response.entries.length) {
    tableRoot.append(
      h("p", { class: "px-4 py-10 text-center text-sm text-slate-500" },
        "No audit entries match these filters."),
    );
  } else {
    tableRoot.append(
      h("table", { class: "table-base" },
        h("thead", {}, h("tr", {},
          h("th", {}, "Time"), h("th", {}, "Actor"), h("th", {}, "Action"),
          h("th", {}, "Target"), h("th", {}, "Status"), h("th", {}, "Source"),
          h("th", {}, "Details"))),
        h("tbody", {},
          response.entries.map((entry) =>
            h("tr", {},
              h("td", { class: "whitespace-nowrap tabular-nums text-slate-500" },
                fmtDateTime(entry.ts)),
              h("td", {},
                h("div", { class: "font-medium" }, entry.actor),
                entry.actor_role
                  ? h("div", { class: "text-xs text-slate-500" }, entry.actor_role)
                  : null),
              h("td", { class: "mono text-xs" }, entry.action),
              h("td", { class: "mono text-xs" }, entry.target || "—"),
              h("td", {}, h("span", { class: STATUS_BADGE[entry.status] ?? "badge-muted" },
                entry.status)),
              h("td", { class: "text-xs text-slate-500" },
                entry.source_ip || entry.computer || "—"),
              h("td", { class: "mono max-w-72 truncate text-xs text-slate-500" },
                entry.details ? JSON.stringify(entry.details) : "—"),
            ),
          )),
      ),
    );
  }

  qs<HTMLElement>("#log-count").textContent =
    `${total} entries · showing ${Math.min(offset + 1, total)}–${Math.min(offset + PAGE_SIZE, total)}`;
  qs<HTMLButtonElement>("#page-prev").disabled = offset === 0;
  qs<HTMLButtonElement>("#page-next").disabled = offset + PAGE_SIZE >= total;

  // Export links carry the active filters.
  const base = filters();
  base.delete("limit");
  base.delete("offset");
  for (const format of ["csv", "json", "pdf"] as const) {
    const link = qs<HTMLAnchorElement>(`#exp-${format}`);
    const params = new URLSearchParams(base);
    params.set("format", format);
    link.href = apiUrl(`/api/logs/export?${params}`);
  }
}

qs<HTMLButtonElement>("#f-apply").addEventListener("click", () => {
  offset = 0;
  void load();
});
qs<HTMLButtonElement>("#page-prev").addEventListener("click", () => {
  offset = Math.max(0, offset - PAGE_SIZE);
  void load();
});
qs<HTMLButtonElement>("#page-next").addEventListener("click", () => {
  offset += PAGE_SIZE;
  void load();
});

const session = await requireSession();
if (can(session, "logs:export")) {
  const group = qs<HTMLElement>("#export-group");
  group.classList.remove("hidden");
  group.classList.add("flex");
}
void load();
