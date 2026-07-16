/** OU tree picker and group picker modals. */

import { api } from "../api";
import { h, icon, clear } from "../dom";
import { ouLabel } from "../format";
import type { GroupInfo, OUNode } from "../types";
import { openModal } from "./modal";

/* ---------- OU picker ------------------------------------------------------------ */

export function pickOU(current?: string | null): Promise<string | null> {
  return new Promise((resolve) => {
    const modal = openModal("Select organizational unit");
    let selected: string | null = current ?? null;
    let resolved = false;

    const confirm = h(
      "button",
      {
        class: "btn-primary",
        disabled: !selected,
        onclick: () => {
          resolved = true;
          modal.close();
          resolve(selected);
        },
      },
      "Select OU",
    );

    const selectedLabel = h(
      "div",
      { class: "mono mb-3 break-all rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300" },
      selected ? selected : "No OU selected",
    );

    function renderNode(node: OUNode, depth: number): HTMLElement {
      const children = h(
        "div",
        { class: depth >= 0 ? "ml-5 border-l border-slate-200 pl-1 dark:border-slate-800" : "" },
        node.children.map((child) => renderNode(child, depth + 1)),
      );
      let expanded = depth < 2;
      children.hidden = !expanded;

      const chevron = node.children.length
        ? icon("chevronDown", "size-3.5")
        : h("span", { class: "inline-block w-3.5" });
      if (node.children.length) {
        chevron.style.transition = "transform 150ms ease-out";
        if (!expanded) chevron.style.transform = "rotate(-90deg)";
      }

      const row = h(
        "button",
        {
          type: "button",
          class: `flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-sm
            transition-[background-color] duration-100 hover:bg-slate-100 dark:hover:bg-slate-800
            ${node.dn === selected ? "bg-accent-700/10 font-medium text-accent-800 dark:bg-accent-400/10 dark:text-accent-300" : ""}`,
          onclick: () => {
            selected = node.dn;
            selectedLabel.textContent = node.dn;
            confirm.removeAttribute("disabled");
            tree.querySelectorAll("button[data-ou]").forEach((b) => {
              b.classList.remove("bg-accent-700/10", "font-medium", "text-accent-800",
                "dark:bg-accent-400/10", "dark:text-accent-300");
            });
            row.classList.add("bg-accent-700/10", "font-medium", "text-accent-800",
              "dark:bg-accent-400/10", "dark:text-accent-300");
          },
          dataset: { ou: node.dn },
        },
        h(
          "span",
          {
            class: "inline-flex shrink-0",
            onclick: (event: Event) => {
              if (!node.children.length) return;
              event.stopPropagation();
              expanded = !expanded;
              children.hidden = !expanded;
              chevron.style.transform = expanded ? "" : "rotate(-90deg)";
            },
          },
          chevron,
        ),
        icon("folder", "size-4 text-slate-400"),
        h("span", {}, node.name),
      );
      return h("div", {}, row, children);
    }

    const tree = h("div", { class: "space-y-0.5" }, h("div", { class: "skeleton h-24" }));
    modal.body.append(selectedLabel, tree);
    modal.footer.append(
      h("button", { class: "btn-secondary", onclick: () => modal.close() }, "Cancel"),
      confirm,
    );

    // Resolve null if the modal is dismissed without confirming.
    const observer = new MutationObserver(() => {
      if (!document.body.contains(modal.panel)) {
        observer.disconnect();
        if (!resolved) resolve(null);
      }
    });
    observer.observe(document.body, { childList: true });

    api.get<{ tree: OUNode[] }>("/api/ou").then(({ tree: nodes }) => {
      clear(tree);
      nodes.forEach((node) => tree.append(renderNode(node, 0)));
    });
  });
}

/* ---------- group picker ----------------------------------------------------------- */

const CATEGORY_BADGE: Record<GroupInfo["category"], string> = {
  security: "badge-muted",
  distribution: "badge-warn",
  m365: "badge-ok",
};

export function pickGroups(preselected: string[]): Promise<string[] | null> {
  return new Promise((resolve) => {
    const modal = openModal("Select groups", { wide: true });
    const chosen = new Set(preselected);
    let category: string | null = null;
    let resolved = false;

    const count = h("span", { class: "text-xs text-slate-500" }, `${chosen.size} selected`);
    const list = h("div", { class: "mt-3 space-y-1" });

    async function load(search = "") {
      clear(list);
      list.append(h("div", { class: "skeleton h-20" }));
      const params = new URLSearchParams({ search });
      if (category) params.set("category", category);
      const { groups } = await api.get<{ groups: GroupInfo[] }>(`/api/groups?${params}`);
      clear(list);
      if (!groups.length) {
        list.append(
          h("p", { class: "py-6 text-center text-sm text-slate-500" },
            "No groups match this search."),
        );
        return;
      }
      for (const group of groups) {
        const checkbox = h("input", {
          type: "checkbox",
          class: "size-4 accent-teal-700",
          checked: chosen.has(group.name),
          onchange: () => {
            checkbox.checked ? chosen.add(group.name) : chosen.delete(group.name);
            count.textContent = `${chosen.size} selected`;
          },
        }) as HTMLInputElement;
        list.append(
          h(
            "label",
            {
              class:
                "flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 transition-[background-color] duration-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/60",
            },
            checkbox,
            h(
              "span",
              { class: "min-w-0 flex-1" },
              h("span", { class: "block text-sm font-medium" }, group.name),
              h("span", { class: "block truncate text-xs text-slate-500" }, group.description),
            ),
            h("span", { class: CATEGORY_BADGE[group.category] }, group.category),
          ),
        );
      }
    }

    let debounce: ReturnType<typeof setTimeout>;
    const search = h("input", {
      class: "input",
      type: "search",
      placeholder: "Search groups…",
      oninput: () => {
        clearTimeout(debounce);
        debounce = setTimeout(() => load((search as HTMLInputElement).value), 250);
      },
    }) as HTMLInputElement;

    const chips = h(
      "div",
      { class: "flex gap-1.5" },
      [null, "security", "distribution", "m365"].map((cat) => {
        const chip = h(
          "button",
          {
            type: "button",
            class: `btn-secondary btn-sm ${cat === category ? "border-accent-600 text-accent-700 dark:text-accent-300" : ""}`,
            onclick: () => {
              category = cat;
              chips.querySelectorAll("button").forEach((b, i) => {
                const active = [null, "security", "distribution", "m365"][i] === category;
                b.classList.toggle("border-accent-600", active);
                b.classList.toggle("text-accent-700", active);
              });
              load(search.value);
            },
          },
          cat === null ? "All" : cat,
        );
        return chip;
      }),
    );

    modal.body.append(
      h("div", { class: "flex flex-wrap items-center gap-2" }, search, chips),
      list,
    );
    modal.footer.append(
      count,
      h("div", { class: "flex-1" }),
      h("button", { class: "btn-secondary", onclick: () => modal.close() }, "Cancel"),
      h(
        "button",
        {
          class: "btn-primary",
          onclick: () => {
            resolved = true;
            modal.close();
            resolve([...chosen]);
          },
        },
        "Apply selection",
      ),
    );

    const observer = new MutationObserver(() => {
      if (!document.body.contains(modal.panel)) {
        observer.disconnect();
        if (!resolved) resolve(null);
      }
    });
    observer.observe(document.body, { childList: true });

    void load();
  });
}

export { ouLabel };
