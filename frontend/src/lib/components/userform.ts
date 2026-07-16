/** Dynamic per-user onboarding form card (used by Create and Clone pages). */

import { api } from "../api";
import { h, icon, qs } from "../dom";
import { initials, ouLabel } from "../format";
import type {
  LicenseInfo, NewUserSpec, UserSummary, ValidationIssue,
} from "../types";
import { pickGroups, pickOU } from "./pickers";

export interface FormContext {
  licenses: LicenseInfo[];
  sharedMailboxes: { name: string; email: string }[];
}

export interface UserFormHandle {
  root: HTMLElement;
  getSpec(): NewUserSpec;
  setIssues(issues: ValidationIssue[]): void;
  setIdentity(spec: NewUserSpec): void;
}

let formSeq = 0;

function field(
  label: string,
  input: HTMLElement,
  options: { span2?: boolean; hint?: string } = {},
): HTMLElement {
  return h(
    "div",
    { class: options.span2 ? "sm:col-span-2" : "" },
    h("label", { class: "label", for: (input as HTMLInputElement).id ?? undefined }, label),
    input,
    options.hint
      ? h("p", { class: "mt-1 text-[11px] text-slate-400 dark:text-slate-500" }, options.hint)
      : null,
  );
}

function section(title: string, ...children: (HTMLElement | null)[]): HTMLElement {
  return h(
    "fieldset",
    { class: "border-t border-slate-100 pt-4 dark:border-slate-800" },
    h(
      "legend",
      { class: "pr-3 text-[11px] font-semibold tracking-wide text-slate-400 uppercase" },
      title,
    ),
    h("div", { class: "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" }, ...children.filter(Boolean) as HTMLElement[]),
  );
}

export function createUserForm(
  index: number,
  ctx: FormContext,
  initial: Partial<NewUserSpec> = {},
  onIdentityChange?: () => void,
): UserFormHandle {
  const uid = `uf${formSeq++}`;
  const val = (v: string | null | undefined) => v ?? "";

  /* --- inputs ------------------------------------------------------------- */
  const inp = (name: string, attrs: Record<string, unknown> = {}) =>
    h("input", { class: "input", id: `${uid}-${name}`, ...attrs }) as HTMLInputElement;

  const first = inp("first", { value: val(initial.first_name), required: true, autocomplete: "off" });
  const last = inp("last", { value: val(initial.last_name), required: true, autocomplete: "off" });
  const displayName = inp("display", { value: val(initial.display_name), placeholder: "auto: First Last" });
  const sam = inp("sam", { value: val(initial.sam_account_name), placeholder: "auto: first.last", class: "input mono" });
  const upn = inp("upn", { value: val(initial.user_principal_name), placeholder: "auto: sam@upn-suffix", class: "input mono" });
  const email = inp("email", { value: val(initial.email), placeholder: "auto: same as UPN", type: "email", class: "input mono" });
  const employeeId = inp("empid", { value: val(initial.employee_id), placeholder: "EMP-…" });
  const employeeType = h(
    "select",
    { class: "input", id: `${uid}-emptype` },
    ["Employee", "Contractor", "Intern", "Vendor"].map((t) =>
      h("option", { value: t, selected: (initial.employee_type ?? "Employee") === t }, t),
    ),
  ) as HTMLSelectElement;
  const description = inp("desc", { value: val(initial.description) });

  const ouInput = inp("ou", {
    value: val(initial.ou), readonly: true, class: "input mono cursor-pointer",
    placeholder: "Browse to choose the target OU…",
    onclick: () => browseOU(),
  });
  const ouBadge = h("span", { class: "badge-muted mt-1" }, initial.ou ? ouLabel(initial.ou) : "required");
  async function browseOU() {
    const dn = await pickOU(ouInput.value || null);
    if (dn) {
      ouInput.value = dn;
      ouBadge.textContent = ouLabel(dn);
    }
  }

  const department = inp("dept", { value: val(initial.department) });
  const company = inp("company", { value: val(initial.company) });
  const jobTitle = inp("title", { value: val(initial.job_title) });
  const costCenter = inp("cc", { value: val(initial.cost_center) });
  const office = inp("office", { value: val(initial.office) });
  const officeLocation = inp("offloc", { value: val(initial.office_location) });

  // Manager autocomplete backed by /api/managers.
  const managerList = h("datalist", { id: `${uid}-mgrlist` });
  const manager = inp("manager", {
    value: val(initial.manager), list: `${uid}-mgrlist`, class: "input mono",
    placeholder: "search by name or username…", autocomplete: "off",
  });
  let managerDebounce: ReturnType<typeof setTimeout>;
  manager.addEventListener("input", () => {
    clearTimeout(managerDebounce);
    const query = manager.value.trim();
    if (query.length < 2) return;
    managerDebounce = setTimeout(async () => {
      const { managers } = await api.get<{ managers: UserSummary[] }>(
        `/api/managers?query=${encodeURIComponent(query)}`,
      );
      managerList.replaceChildren(
        ...managers.map((m) =>
          h("option", { value: m.sam_account_name }, `${m.display_name} — ${m.job_title ?? ""}`),
        ),
      );
    }, 250);
  });

  const phone = inp("phone", { value: val(initial.phone) });
  const mobile = inp("mobile", { value: val(initial.mobile) });
  const country = inp("country", { value: val(initial.country), placeholder: "ISO code, e.g. US" });
  const city = inp("city", { value: val(initial.city) });
  const state = inp("state", { value: val(initial.state) });
  const address = inp("address", { value: val(initial.address) });
  const postal = inp("postal", { value: val(initial.postal_code) });
  const expiration = inp("expiry", { value: val(initial.account_expiration), type: "date" });

  /* --- groups ---------------------------------------------------------------- */
  let groups: string[] = [...(initial.groups ?? [])];
  const groupChips = h("div", { class: "flex flex-wrap gap-1.5" });
  function renderGroupChips() {
    groupChips.replaceChildren(
      ...groups.map((name) =>
        h(
          "span",
          { class: "badge-muted" },
          name,
          h(
            "button",
            {
              type: "button",
              class: "-mr-0.5 opacity-60 hover:opacity-100",
              "aria-label": `Remove ${name}`,
              onclick: () => {
                groups = groups.filter((g) => g !== name);
                renderGroupChips();
              },
            },
            icon("x", "size-3"),
          ),
        ),
      ),
      h(
        "button",
        {
          type: "button",
          class: "btn-secondary btn-sm",
          onclick: async () => {
            const picked = await pickGroups(groups);
            if (picked) {
              groups = picked;
              renderGroupChips();
            }
          },
        },
        icon("users", "size-3.5"),
        groups.length ? "Edit groups" : "Select groups",
      ),
    );
  }
  renderGroupChips();

  /* --- licenses / mailboxes ----------------------------------------------------- */
  const licenseBoxes = ctx.licenses.map((license) => {
    const box = h("input", {
      type: "checkbox", class: "size-4 accent-teal-700",
      value: license.sku_part_number,
      checked: (initial.licenses ?? []).includes(license.sku_part_number),
    }) as HTMLInputElement;
    const available = license.total - license.assigned;
    return {
      box,
      el: h(
        "label",
        { class: "flex cursor-pointer items-center gap-2 text-sm" },
        box,
        h("span", {}, license.display_name),
        h("span", { class: available > 0 ? "badge-muted" : "badge-warn" }, `${available} left`),
      ),
    };
  });

  const mailbox = h("input", {
    type: "checkbox", class: "size-4 accent-teal-700",
    checked: initial.create_mailbox ?? true,
  }) as HTMLInputElement;

  const sharedBoxes = ctx.sharedMailboxes.map((mb) => {
    const box = h("input", {
      type: "checkbox", class: "size-4 accent-teal-700", value: mb.email,
      checked: (initial.shared_mailboxes ?? []).includes(mb.email),
    }) as HTMLInputElement;
    return {
      box,
      el: h(
        "label",
        { class: "flex cursor-pointer items-center gap-2 text-sm" },
        box, h("span", {}, mb.name),
        h("span", { class: "mono text-xs text-slate-500" }, mb.email),
      ),
    };
  });

  /* --- password / home folder / profile ---------------------------------------------- */
  const pwGenerate = h("input", {
    type: "checkbox", class: "size-4 accent-teal-700",
    checked: initial.password?.generate ?? true,
    onchange: () => {
      pwValue.disabled = pwGenerate.checked;
      if (pwGenerate.checked) pwValue.value = "";
    },
  }) as HTMLInputElement;
  const pwValue = inp("pw", {
    type: "password", placeholder: "manual password", autocomplete: "new-password",
    disabled: initial.password?.generate ?? true, value: val(initial.password?.value),
  });
  const pwForce = h("input", {
    type: "checkbox", class: "size-4 accent-teal-700",
    checked: initial.password?.force_change_at_logon ?? true,
  }) as HTMLInputElement;
  const pwNeverExpires = h("input", {
    type: "checkbox", class: "size-4 accent-teal-700",
    checked: initial.password?.never_expires ?? false,
  }) as HTMLInputElement;

  const homeEnabled = h("input", {
    type: "checkbox", class: "size-4 accent-teal-700",
    checked: initial.home_folder?.enabled ?? false,
  }) as HTMLInputElement;
  const homeDrive = h(
    "select",
    { class: "input w-20" },
    "HIJKLMNPQRSTUVWXYZ".split("").map((letter) =>
      h("option", { value: letter, selected: (initial.home_folder?.drive_letter ?? "H") === letter }, `${letter}:`),
    ),
  ) as HTMLSelectElement;
  const profilePath = inp("profpath", {
    value: val(initial.profile?.roaming_profile_path), placeholder: "\\\\FS01\\Profiles\\%username%",
    class: "input mono",
  });
  const logonScript = inp("logon", {
    value: val(initial.profile?.logon_script), placeholder: "logon.bat", class: "input mono",
  });

  /* --- header with live identity preview ----------------------------------------------- */
  const avatar = h("span", {
    class: "flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-700/10 text-xs font-semibold text-accent-800 dark:bg-accent-400/10 dark:text-accent-300",
  }, "–");
  const headTitle = h("span", { class: "text-sm font-semibold" }, `User ${index + 1}`);
  const headSub = h("span", { class: "mono text-xs text-slate-500" }, "");

  function refreshHeader() {
    const name = `${first.value} ${last.value}`.trim();
    avatar.textContent = name ? initials(name) : "–";
    headTitle.textContent = name || `User ${index + 1}`;
    const samPreview = sam.value || (first.value && last.value
      ? `${first.value}.${last.value}`.toLowerCase().replace(/[^a-z0-9.]/g, "")
      : "");
    headSub.textContent = samPreview;
    onIdentityChange?.();
  }
  [first, last, sam].forEach((el) => el.addEventListener("input", refreshHeader));

  const issuesArea = h("div", { class: "mt-3 hidden space-y-1" });

  const body = h(
    "div",
    { class: "space-y-4 px-4 pb-4" },
    section(
      "Identity",
      field("First name *", first), field("Last name *", last), field("Display name", displayName),
      field("Username (SAM)", sam), field("User principal name", upn), field("Email", email),
      field("Employee ID", employeeId), field("Employee type", employeeType),
      field("Description", description),
    ),
    section(
      "Organization",
      h("div", { class: "sm:col-span-2" },
        h("label", { class: "label", for: `${uid}-ou` }, "Organizational unit *"),
        h("div", { class: "flex gap-2" }, ouInput,
          h("button", { type: "button", class: "btn-secondary shrink-0", onclick: () => browseOU() },
            icon("folder", "size-4"), "Browse")),
        ouBadge,
      ),
      field("Department", department), field("Job title", jobTitle),
      h("div", {},
        h("label", { class: "label", for: `${uid}-manager` }, "Manager"),
        manager, managerList),
      field("Company", company), field("Cost center", costCenter),
      field("Office", office), field("Office location", officeLocation),
    ),
    section(
      "Contact & address",
      field("Office phone", phone), field("Mobile", mobile), field("Country", country),
      field("City", city), field("State / province", state), field("Postal code", postal),
      field("Street address", address, { span2: true }),
      field("Account expiration", expiration, { hint: "Leave empty for a permanent account" }),
    ),
    section(
      "Groups & Microsoft 365",
      h("div", { class: "sm:col-span-3" },
        h("span", { class: "label" }, "Group memberships"), groupChips),
      h("div", { class: "sm:col-span-2" },
        h("span", { class: "label" }, "Licenses"),
        h("div", { class: "flex flex-col gap-1.5" }, ...licenseBoxes.map((l) => l.el))),
      h("div", {},
        h("span", { class: "label" }, "Exchange mailbox"),
        h("label", { class: "flex items-center gap-2 text-sm" }, mailbox, "Provision mailbox")),
      h("div", { class: "sm:col-span-3" },
        h("span", { class: "label" }, "Shared mailbox access"),
        h("div", { class: "flex flex-col gap-1.5" }, ...sharedBoxes.map((s) => s.el))),
    ),
    section(
      "Password & profile",
      h("div", {},
        h("span", { class: "label" }, "Password"),
        h("div", { class: "space-y-1.5" },
          h("label", { class: "flex items-center gap-2 text-sm" }, pwGenerate, "Generate secure password"),
          pwValue)),
      h("div", {},
        h("span", { class: "label" }, "Password options"),
        h("div", { class: "space-y-1.5" },
          h("label", { class: "flex items-center gap-2 text-sm" }, pwForce, "Must change at first logon"),
          h("label", { class: "flex items-center gap-2 text-sm" }, pwNeverExpires, "Password never expires"))),
      h("div", {},
        h("span", { class: "label" }, "Home folder"),
        h("div", { class: "flex items-center gap-2" },
          h("label", { class: "flex items-center gap-2 text-sm" }, homeEnabled, "Create home folder"),
          homeDrive)),
      field("Roaming profile path", profilePath), field("Logon script", logonScript),
    ),
    issuesArea,
  );

  let open = index === 0;
  body.hidden = !open;
  const caret = icon("chevronDown", "size-4");

  const header = h(
    "button",
    {
      type: "button",
      class: "flex w-full items-center gap-3 px-4 py-3 text-left",
      "aria-expanded": String(open),
      onclick: () => {
        open = !open;
        body.hidden = !open;
        header.setAttribute("aria-expanded", String(open));
        caret.style.transform = open ? "" : "rotate(-90deg)";
      },
    },
    avatar,
    h("span", { class: "flex min-w-0 flex-1 flex-col" }, headTitle, headSub),
    h("span", { class: "issue-badges flex items-center gap-1.5" }),
    caret,
  );
  caret.style.transition = "transform 150ms ease-out";
  if (!open) caret.style.transform = "rotate(-90deg)";

  const root = h("article", { class: "card overflow-hidden" }, header, body);
  refreshHeader();

  /* --- public API ------------------------------------------------------------------ */
  function getSpec(): NewUserSpec {
    const opt = (input: HTMLInputElement | HTMLSelectElement) =>
      input.value.trim() ? input.value.trim() : null;
    return {
      first_name: first.value.trim(),
      last_name: last.value.trim(),
      display_name: opt(displayName),
      sam_account_name: opt(sam),
      user_principal_name: opt(upn),
      email: opt(email),
      ou: opt(ouInput),
      department: opt(department),
      company: opt(company),
      office: opt(office),
      office_location: opt(officeLocation),
      job_title: opt(jobTitle),
      employee_id: opt(employeeId),
      employee_type: employeeType.value,
      cost_center: opt(costCenter),
      description: opt(description),
      manager: opt(manager),
      phone: opt(phone),
      mobile: opt(mobile),
      country: opt(country),
      city: opt(city),
      state: opt(state),
      address: opt(address),
      postal_code: opt(postal),
      account_expiration: opt(expiration),
      groups: [...groups],
      licenses: licenseBoxes.filter((l) => l.box.checked).map((l) => l.box.value),
      create_mailbox: mailbox.checked,
      shared_mailboxes: sharedBoxes.filter((s) => s.box.checked).map((s) => s.box.value),
      home_folder: { enabled: homeEnabled.checked, drive_letter: homeDrive.value },
      profile: {
        roaming_profile_path: opt(profilePath),
        logon_script: opt(logonScript),
      },
      password: {
        generate: pwGenerate.checked,
        value: pwGenerate.checked ? null : pwValue.value || null,
        force_change_at_logon: pwForce.checked,
        never_expires: pwNeverExpires.checked,
      },
    };
  }

  function setIssues(issues: ValidationIssue[]) {
    issuesArea.replaceChildren();
    const badges = qs<HTMLElement>(".issue-badges", header);
    badges.replaceChildren();
    if (!issues.length) {
      issuesArea.classList.add("hidden");
      badges.append(h("span", { class: "badge-ok" }, icon("check", "size-3"), "valid"));
      return;
    }
    const errors = issues.filter((i) => i.severity === "error").length;
    const warnings = issues.length - errors;
    if (errors) badges.append(h("span", { class: "badge-err" }, `${errors} error${errors > 1 ? "s" : ""}`));
    if (warnings) badges.append(h("span", { class: "badge-warn" }, `${warnings} warning${warnings > 1 ? "s" : ""}`));
    issuesArea.classList.remove("hidden");
    if (errors && body.hidden) header.click();
    for (const issue of issues) {
      issuesArea.append(
        h(
          "div",
          { class: `flex items-start gap-2 rounded-lg px-3 py-2 text-sm ${
            issue.severity === "error"
              ? "bg-rose-50 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300"
              : "bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
          }` },
          icon("warning", "mt-0.5 size-3.5"),
          h("span", {}, h("strong", { class: "font-semibold" }, `${issue.field}: `), issue.message),
        ),
      );
    }
  }

  function setIdentity(spec: NewUserSpec) {
    if (spec.sam_account_name) sam.value = spec.sam_account_name;
    if (spec.user_principal_name) upn.value = spec.user_principal_name;
    if (spec.email) email.value = spec.email;
    if (spec.display_name) displayName.value = spec.display_name;
    refreshHeader();
  }

  return { root, getSpec, setIssues, setIdentity };
}
