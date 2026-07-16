import { api, ApiError, apiUrl } from "../api";
import { openPreviewModal, openProgressModal } from "../components/modal";
import { h, clear, issueBanner, qs } from "../dom";
import { ouLabel } from "../format";
import { requireSession } from "../session";
import { toast } from "../toast";
import type { ExecutionPlan, NewUserSpec, ValidationIssue } from "../types";

interface BulkResponse {
  filename: string;
  rows: number;
  valid: boolean;
  issues: ValidationIssue[];
  users: NewUserSpec[];
}

const dropZone = qs<HTMLElement>("#drop-zone");
const fileInput = qs<HTMLInputElement>("#file-input");
const resultRoot = qs<HTMLElement>("#bulk-result");
const badge = qs<HTMLElement>("#bulk-badge");
const executeBtn = qs<HTMLButtonElement>("#bulk-execute");

let parsed: BulkResponse | null = null;

async function handleFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  toast("info", `Parsing ${file.name}…`);
  try {
    parsed = await api.upload<BulkResponse>("/api/users/bulk", form);
  } catch (error) {
    toast("error", error instanceof ApiError ? error.message : "Upload failed");
    return;
  }
  render();
}

function render() {
  if (!parsed) return;
  resultRoot.classList.remove("hidden");
  qs<HTMLElement>("#bulk-file-label").textContent =
    `${parsed.filename} — ${parsed.rows} row${parsed.rows === 1 ? "" : "s"}`;

  const errors = parsed.issues.filter((issue) => issue.severity === "error").length;
  const warnings = parsed.issues.length - errors;
  badge.className = parsed.valid ? "badge-ok" : "badge-err";
  badge.textContent = parsed.valid
    ? warnings ? `valid · ${warnings} warning(s)` : "all rows valid"
    : `${errors} error(s)`;
  executeBtn.disabled = !parsed.valid;

  const issuesRoot = qs<HTMLElement>("#bulk-issues");
  clear(issuesRoot);
  for (const issue of parsed.issues) {
    issuesRoot.append(
      issueBanner(issue.severity, `Row ${issue.index + 1} · ${issue.field}: `, issue.message),
    );
  }

  const table = qs<HTMLElement>("#bulk-table");
  clear(table);
  table.append(
    h("table", { class: "table-base" },
      h("thead", {}, h("tr", {},
        h("th", {}, "#"), h("th", {}, "Name"), h("th", {}, "Username"), h("th", {}, "OU"),
        h("th", {}, "Department"), h("th", {}, "Groups"), h("th", {}, "Licenses"),
        h("th", {}, "Mailbox"))),
      h("tbody", {},
        parsed.users.map((user, index) =>
          h("tr", {},
            h("td", { class: "tabular-nums text-slate-400" }, String(index + 1)),
            h("td", { class: "font-medium" }, `${user.first_name} ${user.last_name}`),
            h("td", { class: "mono text-xs" }, user.sam_account_name ?? "—"),
            h("td", { class: "text-slate-500" }, ouLabel(user.ou)),
            h("td", { class: "text-slate-500" }, user.department ?? "—"),
            h("td", { class: "text-slate-500" },
              user.groups.length ? `${user.groups.length} groups` : "—"),
            h("td", { class: "mono text-xs text-slate-500" },
              user.licenses.join(", ") || "—"),
            h("td", {}, user.create_mailbox
              ? h("span", { class: "badge-ok" }, "yes")
              : h("span", { class: "badge-muted" }, "no")),
          ),
        )),
    ),
  );
}

executeBtn.addEventListener("click", async () => {
  if (!parsed?.valid) return;
  const plan = await api.post<ExecutionPlan>("/api/users/preview", { users: parsed.users });
  openPreviewModal(plan, async () => {
    try {
      const response = await api.post<{ job_id: string }>("/api/users/create", {
        users: parsed!.users,
      });
      openProgressModal(response.job_id);
      executeBtn.disabled = true;
    } catch (error) {
      toast("error", error instanceof ApiError ? error.message : "Could not start the job");
    }
  });
});

fileInput.addEventListener("change", () => {
  if (fileInput.files?.[0]) void handleFile(fileInput.files[0]);
});
dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("border-accent-600");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("border-accent-600"));
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("border-accent-600");
  const file = event.dataTransfer?.files?.[0];
  if (file) void handleFile(file);
});

// Template download must target the API origin (may differ from this page's).
const templateLink = document.getElementById("template-link") as HTMLAnchorElement | null;
if (templateLink) templateLink.href = apiUrl("/api/users/template.csv");

await requireSession();
