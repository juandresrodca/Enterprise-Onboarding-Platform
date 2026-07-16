/** Dark mode: system preference by default, explicit choice persisted. */

const KEY = "eio-theme";

export function applyStoredTheme(): void {
  const stored = localStorage.getItem(KEY);
  const dark = stored ? stored === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.classList.toggle("dark", dark);
}

export function toggleTheme(): boolean {
  const dark = !document.documentElement.classList.contains("dark");
  document.documentElement.classList.toggle("dark", dark);
  localStorage.setItem(KEY, dark ? "dark" : "light");
  return dark;
}
