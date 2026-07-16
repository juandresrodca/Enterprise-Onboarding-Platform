import { api, ApiError } from "../api";
import { openPreviewModal, openProgressModal } from "../components/modal";
import { createUserForm, type FormContext, type UserFormHandle } from "../components/userform";
import { qs, clear } from "../dom";
import { requireSession } from "../session";
import { toast } from "../toast";
import type { ExecutionPlan, LicenseInfo, ValidationResult } from "../types";

const formsRoot = qs<HTMLElement>("#forms-root");
const actionBar = qs<HTMLElement>("#action-bar");
const summaryBadge = qs<HTMLElement>("#summary-badge");
const validateBtn = qs<HTMLButtonElement>("#validate-btn");
const previewBtn = qs<HTMLButtonElement>("#preview-btn");
const countInput = qs<HTMLInputElement>("#user-count");

let forms: UserFormHandle[] = [];
let ctx: FormContext | null = null;

async function loadContext(): Promise<FormContext> {
  if (ctx) return ctx;
  const [licenses, shared] = await Promise.all([
    api.get<{ licenses: LicenseInfo[] }>("/api/licenses"),
    api.get<{ mailboxes: { name: string; email: string }[] }>("/api/shared-mailboxes"),
  ]);
  ctx = { licenses: licenses.licenses, sharedMailboxes: shared.mailboxes };
  return ctx;
}

function invalidate() {
  previewBtn.disabled = true;
  summaryBadge.className = "badge-muted";
  summaryBadge.textContent = "not validated";
}

async function generateForms() {
  const count = Math.min(Math.max(Number(countInput.value) || 1, 1), 50);
  countInput.value = String(count);
  const context = await loadContext();
  clear(formsRoot);
  forms = [];
  for (let i = 0; i < count; i++) {
    const form = createUserForm(i, context, {}, invalidate);
    forms.push(form);
    formsRoot.append(form.root);
  }
  actionBar.classList.remove("hidden");
  actionBar.classList.add("flex");
  invalidate();
  toast("info", `${count} user form${count > 1 ? "s" : ""} ready`);
}

async function validate(): Promise<ValidationResult | null> {
  const users = forms.map((form) => form.getSpec());
  for (const [i, user] of users.entries()) {
    if (!user.first_name || !user.last_name) {
      toast("warning", `User ${i + 1}: first and last name are required`);
      return null;
    }
  }
  validateBtn.disabled = true;
  validateBtn.textContent = "Validating…";
  try {
    const result = await api.post<ValidationResult>("/api/users/validate", { users });
    forms.forEach((form, index) =>
      form.setIssues(result.issues.filter((issue) => issue.index === index)),
    );
    // Server derived sam/upn/email: reflect them in the forms.
    result.users.forEach((spec, index) => forms[index]?.setIdentity(spec));

    const errors = result.issues.filter((issue) => issue.severity === "error").length;
    const warnings = result.issues.length - errors;
    if (result.valid) {
      summaryBadge.className = "badge-ok";
      summaryBadge.textContent = warnings
        ? `valid · ${warnings} warning${warnings > 1 ? "s" : ""}`
        : "all valid";
      previewBtn.disabled = false;
    } else {
      summaryBadge.className = "badge-err";
      summaryBadge.textContent = `${errors} error${errors > 1 ? "s" : ""} to fix`;
      previewBtn.disabled = true;
      toast("error", "Validation found errors — fix them before executing");
    }
    return result;
  } catch (error) {
    toast("error", error instanceof ApiError ? error.message : "Validation failed");
    return null;
  } finally {
    validateBtn.disabled = false;
    validateBtn.textContent = "Validate";
  }
}

async function previewAndExecute() {
  const result = await validate();
  if (!result?.valid) return;
  const plan = await api.post<ExecutionPlan>("/api/users/preview", { users: result.users });
  openPreviewModal(plan, async () => {
    try {
      const response = await api.post<{ job_id: string }>("/api/users/create", {
        users: result.users,
      });
      openProgressModal(response.job_id, () => invalidate());
    } catch (error) {
      toast("error", error instanceof ApiError ? error.message : "Could not start the job");
    }
  });
}

qs<HTMLButtonElement>("#generate-forms").addEventListener("click", () => void generateForms());
validateBtn.addEventListener("click", () => void validate());
previewBtn.addEventListener("click", () => void previewAndExecute());

await requireSession();
void generateForms();
