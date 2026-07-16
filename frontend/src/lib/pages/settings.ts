import { api, ApiError } from "../api";
import { h, clear, qs } from "../dom";
import { fmtDateTime } from "../format";
import { can, requireSession } from "../session";
import { toast } from "../toast";

interface PlatformSettings {
  app_name: string;
  environment: string;
  demo_mode: boolean;
  entra_enabled: boolean;
  domain_dns: string;
  upn_suffix: string;
  sam_naming_regex: string;
  session_timeout_minutes: number;
  default_home_base_path: string;
  password_policy: {
    min_length: number;
    require_uppercase: boolean;
    require_lowercase: boolean;
    require_digit: boolean;
    require_symbol: boolean;
    disallow_name_parts: boolean;
    generated_length: number;
    max_age_days: number;
  };
}

function row(term: string, value: string | HTMLElement): HTMLElement {
  return h("div", { class: "flex items-baseline justify-between gap-4" },
    h("dt", { class: "text-slate-500 dark:text-slate-400" }, term),
    h("dd", { class: "mono text-right text-[13px]" }, value));
}

const session = await requireSession();

const sessionInfo = qs<HTMLElement>("#session-info");
sessionInfo.append(
  row("Signed in as", session.username),
  row("Display name", session.display_name),
  row("Role", session.role_label),
  row("Auth source", session.auth_source === "entra" ? "Microsoft Entra ID" : "Local (demo)"),
  row("Session expires", fmtDateTime(session.expires_at)),
  row("Permissions", h("span", { class: "text-xs" }, session.permissions.join(", "))),
);

if (!can(session, "settings:read")) {
  qs<HTMLElement>("#platform-info").append(
    h("p", { class: "text-sm text-slate-500" },
      "Platform settings are visible to Administrators and Global Admins."),
  );
  qs<HTMLElement>("#policy-form").append(
    h("p", { class: "text-sm text-slate-500" }, "Not available for your role."),
  );
} else {
  const settings = await api.get<PlatformSettings>("/api/settings");

  qs<HTMLElement>("#platform-info").append(
    row("Application", settings.app_name),
    row("Environment", settings.environment + (settings.demo_mode ? " (demo mode)" : "")),
    row("Entra ID sign-in", settings.entra_enabled ? "configured" : "not configured"),
    row("AD domain", settings.domain_dns),
    row("UPN suffix", `@${settings.upn_suffix}`),
    row("Username convention", settings.sam_naming_regex),
    row("Home folder share", settings.default_home_base_path),
    row("Session timeout", `${settings.session_timeout_minutes} min`),
  );

  const editable = can(session, "settings:write");
  qs<HTMLElement>("#policy-hint").textContent = editable
    ? "editable — you are a Global Admin"
    : "read-only — Global Admin required to edit";

  const form = qs<HTMLElement>("#policy-form");
  const policy = settings.password_policy;

  const numberField = (key: "min_length" | "generated_length" | "max_age_days", label: string, min: number, max: number) => {
    const input = h("input", {
      class: "input", type: "number", min: String(min), max: String(max),
      value: String(policy[key]), disabled: !editable, id: `pol-${key}`,
    }) as HTMLInputElement;
    form.append(h("div", {}, h("label", { class: "label", for: `pol-${key}` }, label), input));
    return input;
  };
  const boolField = (key: keyof typeof policy, label: string) => {
    const input = h("input", {
      type: "checkbox", class: "size-4 accent-teal-700",
      checked: Boolean(policy[key]), disabled: !editable,
    }) as HTMLInputElement;
    form.append(h("label", { class: "flex items-center gap-2 pt-5 text-sm" }, input, label));
    return input;
  };

  const minLength = numberField("min_length", "Minimum length", 8, 64);
  const genLength = numberField("generated_length", "Generated length", 12, 64);
  const maxAge = numberField("max_age_days", "Max age (days)", 0, 730);
  const upper = boolField("require_uppercase", "Require uppercase");
  const lower = boolField("require_lowercase", "Require lowercase");
  const digit = boolField("require_digit", "Require digit");
  const symbol = boolField("require_symbol", "Require symbol");

  if (editable) {
    const save = qs<HTMLButtonElement>("#policy-save");
    save.classList.remove("hidden");
    save.addEventListener("click", async () => {
      try {
        await api.put("/api/settings", {
          min_length: Number(minLength.value),
          generated_length: Number(genLength.value),
          max_age_days: Number(maxAge.value),
          require_uppercase: upper.checked,
          require_lowercase: lower.checked,
          require_digit: digit.checked,
          require_symbol: symbol.checked,
        });
        toast("success", "Password policy updated");
      } catch (error) {
        toast("error", error instanceof ApiError ? error.message : "Update failed");
      }
    });
  }
}
