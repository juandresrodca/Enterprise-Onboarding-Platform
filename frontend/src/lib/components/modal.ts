/** Modal primitives + preview modal + live job progress window (SSE). */

import { apiUrl } from "../api";
import { h, icon, clear } from "../dom";
import { fmtDateTime } from "../format";
import { toast } from "../toast";
import type { ExecutionPlan, Job, JobLogEntry, UserResult } from "../types";

export interface ModalHandle {
  close(): void;
  panel: HTMLElement;
  body: HTMLElement;
  footer: HTMLElement;
}

export function openModal(
  title: string,
  options: { wide?: boolean; persistent?: boolean } = {},
): ModalHandle {
  const backdrop = h("div", { class: "modal-backdrop anim-in" });
  const body = h("div", { class: "min-h-0 flex-1 overflow-y-auto px-5 py-4" });
  const footer = h("div", {
    class:
      "flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-3 dark:border-slate-800",
  });

  const closeBtn = h(
    "button",
    { class: "btn-ghost btn-sm px-1.5", "aria-label": "Close", onclick: () => close() },
    icon("x"),
  );
  const panel = h(
    "div",
    {
      class: `modal-panel anim-in ${options.wide ? "max-w-5xl" : ""}`,
      role: "dialog",
      "aria-modal": "true",
      "aria-label": title,
    },
    h(
      "div",
      {
        class:
          "flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-3.5 dark:border-slate-800",
      },
      h("h2", { class: "text-sm font-semibold" }, title),
      options.persistent ? null : closeBtn,
    ),
    body,
    footer,
  );

  function onKey(event: KeyboardEvent) {
    if (event.key === "Escape" && !options.persistent) close();
  }
  function close() {
    document.removeEventListener("keydown", onKey);
    backdrop.remove();
    panel.remove();
  }
  if (!options.persistent) backdrop.addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  document.body.append(backdrop, panel);
  (panel.querySelector("button, input, a") as HTMLElement | null)?.focus();
  return { close, panel, body, footer };
}

/* ---------- execution preview -------------------------------------------------- */

const ACTION_LABEL: Record<string, string> = {
  create: "Account",
  groups: "Groups",
  licenses: "Licenses",
  mailbox: "Mailbox",
  shared_mailboxes: "Shared mailboxes",
  proxy: "Proxy addresses",
  extensions: "Extension attributes",
  home_folder: "Home folder",
  profile: "Profile",
};

export function openPreviewModal(
  plan: ExecutionPlan,
  onApprove: () => void,
): void {
  const modal = openModal("Review execution plan", { wide: true });

  modal.body.append(
    h(
      "p",
      { class: "mb-4 text-sm text-slate-600 dark:text-slate-400" },
      `${plan.summary}. Nothing has been executed yet — approve to start.`,
    ),
  );

  for (const user of plan.users) {
    const actions = h("div", { class: "mt-3 space-y-2.5" });
    for (const action of user.actions) {
      actions.append(
        h(
          "div",
          { class: "flex gap-3" },
          h(
            "span",
            { class: "badge-muted mt-0.5 w-28 shrink-0 justify-center" },
            ACTION_LABEL[action.kind] ?? action.kind,
          ),
          h(
            "div",
            { class: "min-w-0 text-sm" },
            h("div", { class: "font-medium" }, action.summary),
            action.details.length
              ? h(
                  "div",
                  { class: "mono mt-0.5 break-all text-xs text-slate-500 dark:text-slate-400" },
                  action.details.join(" · "),
                )
              : null,
          ),
        ),
      );
    }
    const warnings = user.warnings.map((w) =>
      h("div", { class: "badge-warn mt-2" }, icon("warning", "size-3"), w),
    );
    modal.body.append(
      h(
        "div",
        { class: "card mb-3 px-4 py-3.5" },
        h(
          "div",
          { class: "flex flex-wrap items-baseline gap-x-3 gap-y-1" },
          h("span", { class: "text-sm font-semibold" }, user.display_name),
          h("span", { class: "mono text-xs text-slate-500" }, user.user_principal_name),
        ),
        actions,
        ...warnings,
      ),
    );
  }

  const approve = h(
    "button",
    {
      class: "btn-primary",
      onclick: () => {
        modal.close();
        onApprove();
      },
    },
    icon("check"),
    `Approve & execute (${plan.total_actions} actions)`,
  );
  modal.footer.append(
    h("button", { class: "btn-secondary", onclick: () => modal.close() }, "Cancel"),
    approve,
  );
}

/* ---------- live job progress (Server-Sent Events) ------------------------------- */

const LOG_COLOR: Record<JobLogEntry["level"], string> = {
  info: "text-slate-400",
  success: "text-accent-400",
  warning: "text-amber-400",
  error: "text-rose-400",
};

export function openProgressModal(jobId: string, onFinished?: (job: Job) => void): void {
  const modal = openModal("Onboarding in progress", { wide: true, persistent: true });

  const bar = h("div", {
    class: "h-2 w-0 rounded-full bg-accent-600 transition-[width] duration-300 ease-out",
  });
  const barLabel = h("span", { class: "text-xs font-medium text-slate-500" }, "Queued…");
  const logView = h("div", {
    class:
      "mono mt-4 max-h-56 min-h-32 overflow-y-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-300",
    role: "log",
    "aria-live": "polite",
  });
  const resultsArea = h("div", { class: "mt-4" });

  modal.body.append(
    h(
      "div",
      { class: "flex items-center justify-between gap-3" },
      h("div", { class: "h-2 flex-1 rounded-full bg-slate-200 dark:bg-slate-800" }, bar),
      barLabel,
    ),
    logView,
    resultsArea,
  );

  const closeBtn = h(
    "button",
    { class: "btn-secondary", disabled: true, onclick: () => modal.close() },
    "Close",
  );
  modal.footer.append(closeBtn);

  function appendLog(entry: JobLogEntry) {
    logView.append(
      h(
        "div",
        {},
        h("span", { class: "text-slate-600" }, `${fmtDateTime(entry.ts).split(", ").pop()} `),
        h("span", { class: LOG_COLOR[entry.level] ?? "" }, entry.message),
      ),
    );
    logView.scrollTop = logView.scrollHeight;
  }

  function setProgress(done: number, total: number, errors: number) {
    const pct = total ? Math.round((done / total) * 100) : 0;
    bar.style.width = `${pct}%`;
    barLabel.textContent = `${done}/${total}${errors ? ` · ${errors} failed` : ""}`;
    if (errors) bar.classList.replace("bg-accent-600", "bg-amber-500");
  }

  function renderResults(job: Job) {
    clear(resultsArea);
    if (!job.results.length) return;
    const rows = job.results.map((result) => resultRow(result));
    resultsArea.append(
      h("h3", { class: "mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase" },
        "Results"),
      h("div", { class: "card divide-y divide-slate-100 dark:divide-slate-800" }, rows),
      job.results.some((r) => r.generated_password)
        ? h(
            "p",
            { class: "mt-2 text-xs text-amber-600 dark:text-amber-400" },
            "Generated passwords are shown only here and are not stored. Hand them over through a secure channel.",
          )
        : null,
    );
  }

  function resultRow(result: UserResult): HTMLElement {
    const row = h(
      "div",
      { class: "flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5" },
      result.status === "success"
        ? h("span", { class: "badge-ok" }, icon("check", "size-3"), "created")
        : h("span", { class: "badge-err" }, icon("x", "size-3"), "failed"),
      h("span", { class: "text-sm font-medium" }, result.display_name),
      h("span", { class: "mono text-xs text-slate-500" }, result.user_principal_name),
      h("span", { class: "min-w-0 flex-1 truncate text-xs text-slate-500" }, result.message),
    );
    if (result.generated_password) {
      const pw = h("code", { class: "mono select-all" }, "••••••••••••");
      let visible = false;
      row.append(
        h(
          "span",
          { class: "flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 dark:bg-slate-800" },
          pw,
          h(
            "button",
            {
              class: "btn-ghost btn-sm px-1",
              "aria-label": "Show password",
              onclick: () => {
                visible = !visible;
                pw.textContent = visible ? result.generated_password! : "••••••••••••";
              },
            },
            icon("eye", "size-3.5"),
          ),
          h(
            "button",
            {
              class: "btn-ghost btn-sm px-1",
              "aria-label": "Copy password",
              onclick: async () => {
                await navigator.clipboard.writeText(result.generated_password!);
                toast("success", `Password for ${result.sam_account_name} copied`);
              },
            },
            icon("copy", "size-3.5"),
          ),
        ),
      );
    }
    return row;
  }

  // withCredentials so the session cookie travels when the API is cross-origin.
  const source = new EventSource(apiUrl(`/api/jobs/${jobId}/events`), {
    withCredentials: true,
  });
  source.onmessage = (event) => {
    const data = JSON.parse(event.data);
    switch (data.type) {
      case "snapshot": {
        const job: Job = data.job;
        job.logs.forEach(appendLog);
        setProgress(job.done, job.total, job.errors);
        renderResults(job);
        if (["completed", "completed_with_errors", "failed"].includes(job.status)) finish(job);
        break;
      }
      case "log":
        appendLog(data.entry);
        break;
      case "progress":
        setProgress(data.done, data.total, data.errors);
        break;
      case "done":
        finish(data.job as Job);
        break;
    }
  };
  source.onerror = () => {
    // The stream closes when the job ends; only warn if we never finished.
    if (!closeBtn.hasAttribute("data-finished")) {
      barLabel.textContent = "Connection lost — check the Logs page";
    }
    source.close();
  };

  function finish(job: Job) {
    source.close();
    setProgress(job.done, job.total, job.errors);
    renderResults(job);
    closeBtn.removeAttribute("disabled");
    closeBtn.setAttribute("data-finished", "1");
    closeBtn.classList.replace("btn-secondary", "btn-primary");
    const ok = job.status === "completed";
    barLabel.textContent = ok
      ? `Done — ${job.total} succeeded`
      : `Finished with ${job.errors} error(s)`;
    toast(ok ? "success" : "warning", ok
      ? `Job finished: ${job.total} user(s) onboarded`
      : `Job finished with ${job.errors} error(s)`);
    onFinished?.(job);
  }
}
