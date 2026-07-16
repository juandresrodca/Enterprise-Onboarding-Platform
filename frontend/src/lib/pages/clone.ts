import { api, ApiError } from "../api";
import { openPreviewModal, openProgressModal } from "../components/modal";
import { h, icon, clear, qs } from "../dom";
import { initials, ouLabel } from "../format";
import { requireSession } from "../session";
import { toast } from "../toast";
import type {
  ExecutionPlan, NewUserSpec, UserDetail, UserSummary, ValidationIssue,
} from "../types";

const OPTION_DEFS: { key: string; label: string; hint: string }[] = [
  { key: "ou", label: "Organizational unit", hint: "same OU as the template" },
  { key: "organization", label: "Organization", hint: "department, company, office, title, cost center" },
  { key: "manager", label: "Manager", hint: "reports to the same manager" },
  { key: "address", label: "Office address", hint: "street, city, state, country" },
  { key: "phones", label: "Office phone", hint: "mobile is personal — never copied" },
  { key: "groups", label: "Groups", hint: "security, distribution and M365 groups" },
  { key: "licenses", label: "Licenses", hint: "same Microsoft 365 SKUs" },
  { key: "shared_mailboxes", label: "Shared mailboxes", hint: "FullAccess + SendAs grants" },
  { key: "proxy_address_pattern", label: "Proxy addresses", hint: "secondary SMTP domains, re-templated" },
  { key: "extension_attributes", label: "Extension attributes", hint: "extensionAttribute1–15" },
  { key: "home_folder", label: "Home folder", hint: "same share, own folder" },
  { key: "logon_script", label: "Logon script", hint: "same script path" },
];

const searchInput = qs<HTMLInputElement>("#source-search");
const resultsBox = qs<HTMLElement>("#source-results");
const sourceCard = qs<HTMLElement>("#source-card");
const configRoot = qs<HTMLElement>("#clone-config");
const optionsRoot = qs<HTMLElement>("#clone-options");
const formsRoot = qs<HTMLElement>("#clone-forms");
const badge = qs<HTMLElement>("#clone-badge");

let source: UserDetail | null = null;
const optionBoxes = new Map<string, HTMLInputElement>();

interface MiniForm {
  root: HTMLElement;
  first: HTMLInputElement;
  last: HTMLInputElement;
  title: HTMLInputElement;
  employeeId: HTMLInputElement;
  issues: HTMLElement;
}
let miniForms: MiniForm[] = [];

/* --- option checkboxes ----------------------------------------------------------- */
for (const def of OPTION_DEFS) {
  const box = h("input", {
    type: "checkbox", class: "mt-0.5 size-4 shrink-0 accent-teal-700", checked: true,
    onchange: () => setBadge("not previewed", "badge-muted"),
  }) as HTMLInputElement;
  optionBoxes.set(def.key, box);
  optionsRoot.append(
    h("label", { class: "flex cursor-pointer items-start gap-2.5 rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-800" },
      box,
      h("span", {},
        h("span", { class: "block text-sm font-medium" }, def.label),
        h("span", { class: "block text-xs text-slate-500" }, def.hint))),
  );
}

/* --- source search -------------------------------------------------------------------- */
let debounce: ReturnType<typeof setTimeout>;
searchInput.addEventListener("input", () => {
  clearTimeout(debounce);
  const query = searchInput.value.trim();
  if (query.length < 2) {
    resultsBox.classList.add("hidden");
    return;
  }
  debounce = setTimeout(async () => {
    const { users } = await api.get<{ users: UserSummary[] }>(
      `/api/users?query=${encodeURIComponent(query)}&limit=8`,
    );
    clear(resultsBox);
    resultsBox.classList.toggle("hidden", users.length === 0);
    for (const user of users) {
      resultsBox.append(
        h("button", {
          type: "button",
          class: "flex w-full items-center gap-3 px-3 py-2 text-left transition-[background-color] duration-100 hover:bg-slate-100 dark:hover:bg-slate-800",
          onclick: () => void selectSource(user.sam_account_name),
        },
        h("span", { class: "flex size-7 items-center justify-center rounded-full bg-accent-700/10 text-xs font-semibold text-accent-800 dark:bg-accent-400/10 dark:text-accent-300" },
          initials(user.display_name)),
        h("span", { class: "min-w-0" },
          h("span", { class: "block truncate text-sm font-medium" }, user.display_name),
          h("span", { class: "block truncate text-xs text-slate-500" },
            `${user.job_title ?? ""} · ${user.department ?? ""}`))),
      );
    }
  }, 250);
});
document.addEventListener("click", (event) => {
  if (!resultsBox.contains(event.target as Node) && event.target !== searchInput) {
    resultsBox.classList.add("hidden");
  }
});

async function selectSource(sam: string) {
  resultsBox.classList.add("hidden");
  const { user } = await api.get<{ user: UserDetail }>(`/api/users/${sam}`);
  source = user;
  searchInput.value = user.display_name;
  clear(sourceCard);
  sourceCard.classList.remove("hidden");
  sourceCard.append(
    h("div", { class: "anim-in flex flex-wrap items-start gap-4 rounded-xl border border-accent-600/30 bg-accent-50/50 px-4 py-3.5 dark:border-accent-400/20 dark:bg-accent-950/20" },
      h("span", { class: "flex size-10 items-center justify-center rounded-full bg-accent-700 text-sm font-semibold text-white dark:bg-accent-600" },
        initials(user.display_name)),
      h("div", { class: "min-w-0 flex-1" },
        h("p", { class: "text-sm font-semibold" }, user.display_name),
        h("p", { class: "text-xs text-slate-600 dark:text-slate-400" },
          `${user.job_title ?? ""} · ${user.department ?? ""} · ${ouLabel(user.ou)}`),
        h("p", { class: "mono mt-0.5 text-xs text-slate-500" }, user.user_principal_name)),
      h("div", { class: "flex flex-wrap gap-1.5" },
        h("span", { class: "badge-muted" }, `${user.groups.length} groups`),
        h("span", { class: "badge-muted" }, `${user.licenses.length} licenses`),
        h("span", { class: "badge-muted" }, `${user.shared_mailboxes.length} shared mailboxes`),
        h("span", { class: "badge-muted" }, `${Object.keys(user.extension_attributes ?? {}).length} ext. attrs`)),
    ),
  );
  configRoot.classList.remove("hidden");
  if (!miniForms.length) generateMiniForms();
}

/* --- new user mini-forms ------------------------------------------------------------- */
function miniForm(index: number): MiniForm {
  const input = (placeholder: string, cls = "input") =>
    h("input", { class: cls, placeholder, autocomplete: "off" }) as HTMLInputElement;
  const first = input("First name *");
  const last = input("Last name *");
  const title = input("Job title (empty = template's)");
  const employeeId = input("Employee ID");
  const issues = h("div", { class: "hidden space-y-1 sm:col-span-4" });
  const root = h("div", { class: "rounded-lg border border-slate-200 px-3 py-3 dark:border-slate-800" },
    h("p", { class: "mb-2 text-xs font-semibold text-slate-500" }, `New user ${index + 1}`),
    h("div", { class: "grid grid-cols-1 gap-2 sm:grid-cols-4" }, first, last, title, employeeId, issues),
  );
  [first, last].forEach((el) =>
    el.addEventListener("input", () => setBadge("not previewed", "badge-muted")));
  return { root, first, last, title, employeeId, issues };
}

function generateMiniForms() {
  const count = Math.min(Math.max(Number(qs<HTMLInputElement>("#clone-count").value) || 1, 1), 20);
  clear(formsRoot);
  miniForms = [];
  for (let i = 0; i < count; i++) {
    const form = miniForm(i);
    miniForms.push(form);
    formsRoot.append(form.root);
  }
  setBadge("not previewed", "badge-muted");
}

function setBadge(text: string, cls: string) {
  badge.textContent = text;
  badge.className = cls;
}

function buildRequest(): { source_sam: string; options: Record<string, boolean>; users: Partial<NewUserSpec>[] } | null {
  if (!source) {
    toast("warning", "Pick a template user first");
    return null;
  }
  const users: Partial<NewUserSpec>[] = [];
  for (const [i, form] of miniForms.entries()) {
    if (!form.first.value.trim() || !form.last.value.trim()) {
      toast("warning", `New user ${i + 1}: first and last name are required`);
      return null;
    }
    users.push({
      first_name: form.first.value.trim(),
      last_name: form.last.value.trim(),
      job_title: form.title.value.trim() || null,
      employee_id: form.employeeId.value.trim() || null,
    });
  }
  const options: Record<string, boolean> = {};
  optionBoxes.forEach((box, key) => (options[key] = box.checked));
  return { source_sam: source.sam_account_name, options, users };
}

function showIssues(issues: ValidationIssue[]) {
  miniForms.forEach((form, index) => {
    const own = issues.filter((issue) => issue.index === index);
    form.issues.replaceChildren();
    form.issues.classList.toggle("hidden", own.length === 0);
    for (const issue of own) {
      form.issues.append(
        h("div", {
          class: `flex items-start gap-2 rounded-lg px-3 py-2 text-sm ${
            issue.severity === "error"
              ? "bg-rose-50 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300"
              : "bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"}`,
        },
        icon("warning", "mt-0.5 size-3.5"),
        h("span", {}, h("strong", { class: "font-semibold" }, `${issue.field}: `), issue.message)),
      );
    }
  });
}

qs<HTMLButtonElement>("#clone-generate").addEventListener("click", generateMiniForms);

qs<HTMLButtonElement>("#clone-preview").addEventListener("click", async () => {
  const body = buildRequest();
  if (!body) return;
  let response: { valid: boolean; issues: ValidationIssue[]; plan: ExecutionPlan };
  try {
    response = await api.post("/api/users/clone", body);
  } catch (error) {
    toast("error", error instanceof ApiError ? error.message : "Clone preparation failed");
    return;
  }
  showIssues(response.issues);
  const errors = response.issues.filter((issue) => issue.severity === "error").length;
  if (!response.valid) {
    setBadge(`${errors} error(s) to fix`, "badge-err");
    return;
  }
  setBadge("plan ready", "badge-ok");
  openPreviewModal(response.plan, async () => {
    try {
      const started = await api.post<{ job_id: string }>("/api/users/clone?execute=true", body);
      openProgressModal(started.job_id);
    } catch (error) {
      toast("error", error instanceof ApiError ? error.message : "Could not start the job");
    }
  });
});

await requireSession();
