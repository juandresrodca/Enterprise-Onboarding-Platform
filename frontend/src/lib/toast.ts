/** Toast notifications (top-right, auto-dismiss, accessible). */

import { h, icon } from "./dom";

type ToastKind = "success" | "error" | "warning" | "info";

const KIND_STYLES: Record<ToastKind, string> = {
  success: "border-accent-600/40 text-accent-900 dark:text-accent-200",
  error: "border-rose-500/50 text-rose-900 dark:text-rose-200",
  warning: "border-amber-500/50 text-amber-900 dark:text-amber-200",
  info: "border-slate-300 text-slate-800 dark:border-slate-600 dark:text-slate-200",
};

function container(): HTMLElement {
  let el = document.getElementById("toast-root");
  if (!el) {
    el = h("div", {
      id: "toast-root",
      class: "fixed top-4 right-4 z-[70] flex w-80 flex-col gap-2",
      "aria-live": "polite",
    });
    document.body.append(el);
  }
  return el;
}

const KIND_ICONS = {
  success: "check",
  error: "x",
  warning: "warning",
  info: "info",
} as const;

export function toast(kind: ToastKind, message: string, timeout = 4500): void {
  const iconName = KIND_ICONS[kind];
  const el = h(
    "div",
    {
      class: `anim-in flex items-start gap-2.5 rounded-lg border bg-white/95 px-3.5 py-2.5
        text-sm shadow-lg shadow-slate-900/10 backdrop-blur dark:bg-slate-900/95
        ${KIND_STYLES[kind]}`,
      role: "status",
    },
    icon(iconName, "size-4 mt-0.5"),
    h("div", { class: "min-w-0 flex-1 break-words" }, message),
  );
  const dismiss = h(
    "button",
    { class: "btn-ghost btn-sm -mr-1 -mt-0.5 px-1.5", "aria-label": "Dismiss", onclick: () => el.remove() },
    icon("x", "size-3.5"),
  );
  el.append(dismiss);
  container().append(el);
  if (timeout > 0) setTimeout(() => el.remove(), timeout);
}
