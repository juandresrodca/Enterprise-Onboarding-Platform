/** Minimal client-side i18n.
 *
 * English is the build-time default: Astro frontmatter runs on the server,
 * where localStorage doesn't exist, so t() there always resolves to "en" -
 * GitHub Pages' static HTML is guaranteed to render English first. A user's
 * language choice is persisted the same way as the theme (localStorage) and
 * applied client-side by swapping the text of every [data-i18n] element -
 * never baked into the page markup itself.
 */

import en from "../locales/en.json";
import es from "../locales/es.json";

export type Locale = "en" | "es";

const DICTS: Record<Locale, Record<string, unknown>> = { en, es };
const KEY = "eio-lang";

export function getLocale(): Locale {
  if (typeof localStorage === "undefined") return "en";
  return localStorage.getItem(KEY) === "es" ? "es" : "en";
}

export function setLocale(locale: Locale): void {
  localStorage.setItem(KEY, locale);
}

function lookup(dict: Record<string, unknown>, key: string): string | undefined {
  const value = key.split(".").reduce<unknown>(
    (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined),
    dict,
  );
  return typeof value === "string" ? value : undefined;
}

export function t(key: string, locale: Locale = getLocale()): string {
  return lookup(DICTS[locale], key) ?? lookup(DICTS.en, key) ?? key;
}

/** Re-translate every tagged element to the current locale. Call after
 * setLocale() and once on page load (locale may differ from the English
 * markup Astro rendered at build time). */
export function applyTranslations(root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n!);
  });
  root.querySelectorAll<HTMLElement>("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAria!));
  });
}
