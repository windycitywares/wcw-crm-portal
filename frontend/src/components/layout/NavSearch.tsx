"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { NavGroup, NavItem } from "./nav";

interface Hit { item: NavItem; where: string }

/** Every page the menu can reach, once, with the section it lives in ("Settings · Lists"). */
function entries(sections: { prefix?: string; groups: NavGroup[] }[]): Hit[] {
  const seen = new Set<string>();
  const out: Hit[] = [];
  for (const { prefix, groups } of sections) {
    for (const g of groups) {
      let parent: NavItem | undefined;
      for (const item of g.items) {
        if (!item.child) parent = item;
        if (item.hidden || seen.has(item.href)) continue;
        seen.add(item.href);
        const where = [prefix, g.label, item.child && parent && parent !== item ? parent.label : undefined].filter(Boolean).join(" · ");
        out.push({ item, where });
      }
    }
  }
  return out;
}

const norm = (s: string) => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");

/** Every word typed has to appear in the page's name, its section or its keywords; a name match ranks first. */
function search(all: Hit[], q: string): Hit[] {
  const words = norm(q).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  return all
    .map((h) => {
      const label = norm(h.item.label);
      const hay = `${label} ${norm(h.where)} ${norm(h.item.keywords ?? "")}`;
      if (!words.every((w) => hay.includes(w))) return null;
      const score = label.startsWith(words[0]) ? 0 : words.every((w) => label.includes(w)) ? 1 : 2;
      return { h, score };
    })
    .filter((x): x is { h: Hit; score: number } => !!x)
    .sort((a, b) => a.score - b.score || a.h.item.label.localeCompare(b.h.item.label))
    .map((x) => x.h);
}

function Mark({ text, q }: { text: string; q: string }) {
  const w = norm(q).split(/\s+/).filter(Boolean).sort((a, b) => b.length - a.length)[0];
  const i = w ? norm(text).indexOf(w) : -1;
  if (i < 0) return <>{text}</>;
  return <>{text.slice(0, i)}<mark className="rounded-sm bg-gold/30 text-inherit">{text.slice(i, i + w.length)}</mark>{text.slice(i + w.length)}</>;
}

/** A filter box at the top of the sidebar: type part of a page's name (or what it's for — "sku", "deleted") and jump
 *  straight to it, from any menu, Settings included. Enter opens the first match, ↓/↑ walk the list, Esc clears. */
export function NavSearch({ sections, onNavigate, children }: {
  sections: { prefix?: string; groups: NavGroup[] }[];
  onNavigate?: () => void;
  /** The normal menu, shown while nothing is typed. */
  children: React.ReactNode;
}) {
  const { can } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const uid = useId();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const all = useMemo(() => entries(sections).filter((h) => !h.item.permission || can(h.item.permission)), [sections, can]);
  const hits = useMemo(() => search(all, q).slice(0, 12), [all, q]);
  useEffect(() => setActive(0), [q]);
  useEffect(() => setQ(""), [pathname]);

  // "/" jumps to the box from anywhere that isn't already a text field.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(input|textarea|select)$/i.test(t.tagName))) return;
      if (!input.current || input.current.offsetParent === null) return;
      e.preventDefault();
      input.current.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (h: Hit | undefined) => {
    if (!h) return;
    setQ("");
    onNavigate?.();
    router.push(h.item.href);
  };

  return (
    <>
      <div className="relative mb-3">
        <label htmlFor={`${uid}-q`} className="sr-only">Find a page</label>
        <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <input
          ref={input}
          id={`${uid}-q`}
          type="search"
          role="combobox"
          aria-expanded={q.trim() !== ""}
          aria-controls={`${uid}-results`}
          aria-activedescendant={hits[active] ? `${uid}-hit-${active}` : undefined}
          autoComplete="off"
          maxLength={60}
          placeholder="Find a page…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, hits.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
            else if (e.key === "Enter") { e.preventDefault(); go(hits[active]); }
            else if (e.key === "Escape") { setQ(""); }
          }}
          className="h-9 w-full rounded-[var(--radius-control)] border border-line bg-surface pl-8 pr-8 text-sm text-ink placeholder:text-muted/80 hover:border-ink/40 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/25 [&::-webkit-search-cancel-button]:hidden"
        />
        {q ? (
          <button type="button" onClick={() => { setQ(""); input.current?.focus(); }}
            className="absolute right-1.5 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded text-muted hover:bg-sand hover:text-ink">
            <Icon name="close" className="size-3.5" />
            <span className="sr-only">Clear the search</span>
          </button>
        ) : (
          <kbd aria-hidden="true" className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-line px-1.5 text-[0.6875rem] text-muted">/</kbd>
        )}
      </div>
      {q.trim() ? (
        <div>
          <ul id={`${uid}-results`} role="listbox" aria-label="Pages" className="space-y-0.5">
            {hits.map((h, i) => (
              <li key={h.item.href} id={`${uid}-hit-${i}`} role="option" aria-selected={i === active}>
                <Link href={h.item.href} onClick={() => { setQ(""); onNavigate?.(); }} onMouseEnter={() => setActive(i)}
                  className={cn("flex items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-sm",
                    i === active ? "bg-sand text-ink" : "text-ink/85 hover:bg-sand")}>
                  <Icon name={h.item.icon} className="size-4 shrink-0 text-muted" />
                  <span className="min-w-0">
                    <span className="block truncate font-medium"><Mark text={h.item.label} q={q} /></span>
                    {h.where && <span className="block truncate text-xs text-muted">{h.where}</span>}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {hits.length === 0 && <p className="px-3 py-4 text-sm text-muted">No page matches “{q.trim()}”.</p>}
          <p role="status" className="sr-only">{hits.length} {hits.length === 1 ? "page" : "pages"} found</p>
        </div>
      ) : children}
    </>
  );
}
