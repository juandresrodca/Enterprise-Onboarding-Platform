import { api, ApiError } from "../api";
import { openPreviewModal, openProgressModal } from "../components/modal";
import { pickOU } from "../components/pickers";
import { h, clear, issueBanner, qs } from "../dom";
import { initials } from "../format";
import { requireSession } from "../session";
import { toast } from "../toast";
import type {
  OffboardExecutionPlan, OffboardOptions, OffboardTarget, UserSummary, ValidationIssue,
} from "../types";

const searchInput = qs<HTMLInputElement>("#offboard-search");
const resultsBox = qs<HTMLElement>("#offboard-results");
const selectedRoot = qs<HTMLElement>("#offboard-selected");
const actionBar = qs<HTMLElement>("#offboard-action-bar");
const badge = qs<HTMLElement>("#offboard-badge");
const previewBtn = qs<HTMLButtonElement>("#offboard-preview-btn");
const moveOuInput = qs<HTMLInputElement>("#opt-move-ou");
const handoverInput = qs<HTMLInputElement>("#opt-handover");
const handoverList = qs<HTMLElement>("#offboard-handover-list");

const selected = new Map<string, UserSummary>();
const reasons = new Map<string, string>();
const issuesByCard = new Map<string, HTMLElement>();

function invalidate() {
  badge.className = "badge-muted";
  badge.textContent = "not previewed";
}

/* --- source search: click a result to add it to the offboard batch ------------------- */
let searchDebounce: ReturnType<typeof setTimeout>;
searchInput.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  const query = searchInput.value.trim();
  if (query.length < 2) {
    resultsBox.classList.add("hidden");
    return;
  }
  searchDebounce = setTimeout(async () => {
    const { users } = await api.get<{ users: UserSummary[] }>(
      `/api/users?query=${encodeURIComponent(query)}&limit=8`,
    );
    clear(resultsBox);
    const candidates = users.filter((u) => !selected.has(u.sam_account_name));
    resultsBox.classList.toggle("hidden", candidates.length === 0);
    for (const user of candidates) {
      resultsBox.append(
        h("button", {
          type: "button",
          class: "flex w-full items-center gap-3 px-3 py-2 text-left transition-[background-color] duration-100 hover:bg-slate-100 dark:hover:bg-slate-800",
          onclick: () => addUser(user),
        },
        h("span", { class: "flex size-7 items-center justify-center rounded-full bg-accent-700/10 text-xs font-semibold text-accent-800 dark:bg-accent-400/10 dark:text-accent-300" },
          initials(user.display_name)),
        h("span", { class: "min-w-0" },
          h("span", { class: "block truncate text-sm font-medium" }, user.display_name),
          h("span", { class: "block truncate text-xs text-slate-500" },
            `${user.job_title ?? ""} · ${user.department ?? ""}${user.enabled ? "" : " · already disabled"}`))),
      );
    }
  }, 250);
});
document.addEventListener("click", (event) => {
  if (!resultsBox.contains(event.target as Node) && event.target !== searchInput) {
    resultsBox.classList.add("hidden");
  }
});

function addUser(user: UserSummary) {
  selected.set(user.sam_account_name, user);
  searchInput.value = "";
  resultsBox.classList.add("hidden");
  renderSelected();
  invalidate();
}

function removeUser(sam: string) {
  selected.delete(sam);
  reasons.delete(sam);
  issuesByCard.delete(sam);
  renderSelected();
  invalidate();
}

function renderSelected() {
  clear(selectedRoot);
  actionBar.classList.toggle("hidden", selected.size === 0);
  actionBar.classList.toggle("flex", selected.size > 0);
  for (const [sam, user] of selected) {
    const reasonInput = h("input", {
      class: "input", placeholder: "Reason (optional) — e.g. Resigned, Terminated…",
      value: reasons.get(sam) ?? "",
      oninput: (e: Event) => reasons.set(sam, (e.target as HTMLInputElement).value),
    }) as HTMLInputElement;
    const issuesArea = h("div", { class: "mt-2 hidden space-y-1" });
    issuesByCard.set(sam, issuesArea);
    selectedRoot.append(
      h("div", { class: "card px-4 py-3" },
        h("div", { class: "flex flex-wrap items-center gap-3" },
          h("span", { class: "flex size-9 shrink-0 items-center justify-center rounded-full bg-rose-100 text-sm font-semibold text-rose-800 dark:bg-rose-950 dark:text-rose-300" },
            initials(user.display_name)),
          h("div", { class: "min-w-0 flex-1" },
            h("div", { class: "flex flex-wrap items-baseline gap-x-2" },
              h("span", { class: "text-sm font-semibold" }, user.display_name),
              h("span", { class: "mono text-xs text-slate-500" }, user.sam_account_name),
              !user.enabled ? h("span", { class: "badge-warn" }, "already disabled") : null),
            h("span", { class: "block text-xs text-slate-500" },
              `${user.job_title ?? ""} · ${user.department ?? ""}`)),
          h("div", { class: "w-56" }, reasonInput),
          h("button", {
            type: "button", class: "btn-ghost btn-sm", "aria-label": `Remove ${user.display_name}`,
            onclick: () => removeUser(sam),
          }, "Remove"),
        ),
        issuesArea,
      ),
    );
  }
}

/* --- manager autocomplete for mailbox handover -------------------------------------- */
let handoverDebounce: ReturnType<typeof setTimeout>;
handoverInput.addEventListener("input", () => {
  clearTimeout(handoverDebounce);
  invalidate();
  const query = handoverInput.value.trim();
  if (query.length < 2) return;
  handoverDebounce = setTimeout(async () => {
    const { managers } = await api.get<{ managers: UserSummary[] }>(
      `/api/managers?query=${encodeURIComponent(query)}`,
    );
    handoverList.replaceChildren(
      ...managers.map((m) =>
        h("option", { value: m.sam_account_name }, `${m.display_name} — ${m.job_title ?? ""}`)),
    );
  }, 250);
});

/* --- move-to-OU picker ---------------------------------------------------------------- */
qs<HTMLButtonElement>("#opt-move-ou-browse").addEventListener("click", async () => {
  const dn = await pickOU(moveOuInput.value || null);
  if (dn) {
    moveOuInput.value = dn;
    invalidate();
  }
});

for (const id of [
  "opt-revoke-licenses", "opt-remove-groups", "opt-keep-dls",
  "opt-reset-password", "opt-convert-mailbox",
]) {
  document.getElementById(id)?.addEventListener("change", invalidate);
}

/* --- build the request + preview/execute --------------------------------------------- */
function buildOptions(): OffboardOptions {
  return {
    revoke_licenses: qs<HTMLInputElement>("#opt-revoke-licenses").checked,
    remove_from_groups: qs<HTMLInputElement>("#opt-remove-groups").checked,
    keep_distribution_lists: qs<HTMLInputElement>("#opt-keep-dls").checked,
    convert_mailbox_to_shared: qs<HTMLInputElement>("#opt-convert-mailbox").checked,
    reset_password: qs<HTMLInputElement>("#opt-reset-password").checked,
    grant_mailbox_access_to: handoverInput.value.trim() || null,
    move_to_ou: moveOuInput.value.trim() || null,
  };
}

function buildTargets(): OffboardTarget[] {
  return [...selected.entries()].map(([sam, user]) => ({
    sam_account_name: sam,
    reason: reasons.get(sam)?.trim() || null,
  }));
}

function showIssues(issues: ValidationIssue[]) {
  const order = [...selected.keys()];
  for (const area of issuesByCard.values()) {
    area.replaceChildren();
    area.classList.add("hidden");
  }
  for (const issue of issues) {
    const sam = order[issue.index];
    const area = sam ? issuesByCard.get(sam) : undefined;
    if (!area) continue;
    area.classList.remove("hidden");
    area.append(issueBanner(issue.severity, `${issue.field}: `, issue.message));
  }
}

previewBtn.addEventListener("click", async () => {
  if (selected.size === 0) {
    toast("warning", "Select at least one user to offboard");
    return;
  }
  const body = { users: buildTargets(), options: buildOptions() };
  previewBtn.disabled = true;
  previewBtn.textContent = "Validating…";
  let plan: OffboardExecutionPlan;
  try {
    plan = await api.post<OffboardExecutionPlan>("/api/offboard/preview", body);
  } catch (error) {
    toast("error", error instanceof ApiError ? error.message : "Preview failed");
    previewBtn.disabled = false;
    previewBtn.textContent = "Preview offboarding";
    return;
  }
  previewBtn.disabled = false;
  previewBtn.textContent = "Preview offboarding";

  showIssues(plan.issues);
  const errors = plan.issues.filter((i) => i.severity === "error").length;
  if (errors) {
    badge.className = "badge-err";
    badge.textContent = `${errors} error${errors > 1 ? "s" : ""} to fix`;
    toast("error", "Validation found errors — fix them before offboarding");
    return;
  }
  const warnings = plan.issues.length;
  badge.className = "badge-ok";
  badge.textContent = warnings ? `plan ready · ${warnings} warning(s)` : "plan ready";

  openPreviewModal(plan, async () => {
    try {
      const started = await api.post<{ job_id: string }>("/api/offboard", body);
      openProgressModal(started.job_id, () => invalidate(), {
        title: "Offboarding in progress", verb: "offboarded",
      });
    } catch (error) {
      toast("error", error instanceof ApiError ? error.message : "Could not start the job");
    }
  });
});

await requireSession();
