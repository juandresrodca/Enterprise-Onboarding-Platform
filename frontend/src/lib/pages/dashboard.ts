import { api } from "../api";
import { h, icon, clear, qs } from "../dom";
import { fmtDateTime, ouLabel, timeAgo } from "../format";
import { requireSession } from "../session";
import { toast } from "../toast";
import type { DashboardData, Job } from "../types";

const STATUS_BADGE: Record<string, string> = {
  completed: "badge-ok",
  completed_with_errors: "badge-warn",
  failed: "badge-err",
  running: "badge-muted",
  queued: "badge-muted",
};

function statCard(label: string, value: string | number, hint: string): HTMLElement {
  return h(
    "div",
    { class: "card anim-in px-4 py-3.5" },
    h("p", { class: "text-xs font-medium text-slate-500 dark:text-slate-400" }, label),
    h("p", { class: "mt-1 text-2xl font-semibold tabular-nums tracking-tight" }, String(value)),
    h("p", { class: "mt-0.5 text-[11px] text-slate-400 dark:text-slate-500" }, hint),
  );
}

async function render() {
  await requireSession();
  let data: DashboardData;
  try {
    data = await api.get<DashboardData>("/api/dashboard");
  } catch {
    toast("error", "Could not load the dashboard");
    return;
  }

  const cards = qs<HTMLElement>("#stat-cards");
  clear(cards);
  cards.append(
    statCard("Total users", data.stats.total_users, `${data.stats.enabled_users} enabled`),
    statCard("Created · last 7 days", data.stats.created_last_7_days, "via onboarding & sync"),
    statCard("Pending onboarding", data.pending_jobs, "queued or running jobs"),
    statCard("Errors · last 24 h", data.errors_24h, "from the audit trail"),
  );

  // Recent users table
  const recent = qs<HTMLElement>("#recent-users");
  clear(recent);
  const rows = data.stats.recent_users.map((user) =>
    h(
      "tr",
      {},
      h("td", {},
        h("div", { class: "font-medium" }, user.display_name),
        h("div", { class: "mono text-xs text-slate-500" }, user.sam_account_name)),
      h("td", { class: "text-slate-500" }, user.job_title ?? "—"),
      h("td", { class: "text-slate-500" }, user.department ?? "—"),
      h("td", { class: "text-slate-500" }, ouLabel(user.ou)),
      h("td", {},
        user.source === "onboarding"
          ? h("span", { class: "badge-ok" }, "onboarded")
          : h("span", { class: "badge-muted" }, "directory")),
      h("td", { class: "whitespace-nowrap text-slate-500" }, timeAgo(user.created_at)),
    ),
  );
  recent.append(
    h("table", { class: "table-base" },
      h("thead", {}, h("tr", {},
        h("th", {}, "User"), h("th", {}, "Title"), h("th", {}, "Department"),
        h("th", {}, "OU"), h("th", {}, "Source"), h("th", {}, "Created"))),
      h("tbody", {}, rows)),
  );

  // License bars
  const licenses = qs<HTMLElement>("#license-usage");
  clear(licenses);
  for (const license of data.stats.licenses) {
    const pct = license.total ? Math.round((license.assigned / license.total) * 100) : 0;
    licenses.append(
      h("div", {},
        h("div", { class: "mb-1 flex items-baseline justify-between gap-2" },
          h("span", { class: "text-sm font-medium" }, license.display_name),
          h("span", { class: "text-xs tabular-nums text-slate-500" },
            `${license.assigned}/${license.total}`)),
        h("div", { class: "h-1.5 rounded-full bg-slate-200 dark:bg-slate-800" },
          h("div", {
            class: `h-1.5 rounded-full ${pct >= 90 ? "bg-amber-500" : "bg-accent-600"}`,
            style: `width:${pct}%`,
          })),
      ),
    );
  }

  // Activity feed
  const feed = qs<HTMLElement>("#activity-feed");
  clear(feed);
  if (!data.recent_activity.length) {
    feed.append(h("p", { class: "px-4 py-6 text-center text-sm text-slate-500" },
      "No activity yet. Create your first user to see the audit trail here."));
  }
  for (const entry of data.recent_activity) {
    feed.append(
      h("div", { class: "flex items-center gap-3 px-4 py-2.5" },
        entry.status === "success"
          ? icon("check", "size-4 text-accent-600")
          : entry.status === "warning"
            ? icon("warning", "size-4 text-amber-500")
            : icon("x", "size-4 text-rose-500"),
        h("div", { class: "min-w-0 flex-1" },
          h("p", { class: "truncate text-sm" },
            h("span", { class: "font-medium" }, entry.actor),
            h("span", { class: "text-slate-500" }, ` · ${entry.action}`),
            entry.target ? h("span", { class: "mono text-xs text-slate-500" }, ` → ${entry.target}`) : null),
        ),
        h("span", { class: "shrink-0 text-xs whitespace-nowrap text-slate-400" }, timeAgo(entry.ts)),
      ),
    );
  }

  // Jobs
  const jobList = qs<HTMLElement>("#job-list");
  clear(jobList);
  if (!data.recent_jobs.length) {
    jobList.append(h("p", { class: "px-4 py-6 text-center text-sm text-slate-500" },
      "No onboarding jobs yet."));
  }
  for (const job of data.recent_jobs as Job[]) {
    jobList.append(
      h("div", { class: "px-4 py-2.5" },
        h("div", { class: "flex items-center justify-between gap-2" },
          h("span", { class: "mono text-xs" }, `${job.type} · ${job.id}`),
          h("span", { class: STATUS_BADGE[job.status] ?? "badge-muted" },
            job.status.replaceAll("_", " "))),
        h("p", { class: "mt-0.5 text-xs text-slate-500" },
          `${job.done}/${job.total} users · by ${job.created_by} · ${fmtDateTime(job.created_at)}`),
      ),
    );
  }
}

void render();
