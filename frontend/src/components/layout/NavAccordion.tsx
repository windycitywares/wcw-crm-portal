"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { activeHref, type NavGroup, type NavItem } from "./nav";

/*
 * The sidebar as an accordion, two levels deep:
 *  - a labelled section (Support, Customers, Marketing…) opens and closes from its heading;
 *  - an item with sub-pages (Campaigns → Templates, Audiences…; Etsy → Orders, Listings…) folds them under a
 *    small chevron beside it.
 * Going to a page opens its section and branch. What someone opens or closes is
 * remembered in this browser, so the menu stays the way they left it. On the narrow icon rail everything is
 * shown flat (there is nothing to fold into).
 */

const KEY = "wcw-crm-nav";
type Saved = Record<string, boolean>;

function readSaved(): Saved {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Saved) : {};
  } catch {
    return {};
  }
}

function writeSaved(value: Saved) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    /* private window or storage blocked: the menu still works, it just won't remember */
  }
}

/** A parent and the sub-pages listed right after it (`child: true`). */
interface Branch {
  item: NavItem;
  children: NavItem[];
}

function branches(items: NavItem[]): Branch[] {
  const out: Branch[] = [];
  for (const item of items) {
    if (item.child && out.length) out[out.length - 1].children.push(item);
    else out.push({ item, children: [] });
  }
  return out;
}

/** Smoothly opens to its content's height (CSS grid rows), instantly when reduced motion is asked for. */
function Collapse({ open, id, children }: { open: boolean; id: string; children: React.ReactNode }) {
  return (
    <div
      id={id}
      className={cn(
        "grid transition-[grid-template-rows,opacity] duration-200 ease-out motion-reduce:transition-none",
        open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
      )}
      inert={!open}
    >
      <div className="min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}

function NavLink({ item, active, collapsed, sub, onNavigate }: {
  item: NavItem; active: boolean; collapsed: boolean; sub?: boolean; onNavigate?: () => void;
}) {
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      title={collapsed ? item.label : undefined}
      className={cn(
        "font-admin group relative flex min-w-0 flex-1 items-center gap-3 rounded-[var(--radius-control)] py-2 transition-[color,background-color,transform] duration-150 focus-visible:outline-offset-0",
        collapsed ? "justify-center px-2" : "px-3",
        sub ? "text-[0.875rem]" : "text-[0.95rem]",
        active ? "bg-sand font-bold text-ink" : "text-ink hover:bg-sand/60 hover:text-accent motion-safe:hover:translate-x-0.5",
      )}
    >
      {active && <span aria-hidden="true" className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-accent" />}
      <Icon name={item.icon} className={cn("size-[1.15rem] shrink-0", active ? "text-accent" : "text-muted group-hover:text-accent")} />
      {collapsed ? <span className="sr-only">{item.label}</span> : <span className="truncate">{item.label}</span>}
    </Link>
  );
}

function BranchItem({ branch, current, open, onToggle, collapsed, onNavigate }: {
  branch: Branch; current?: string; open: boolean; onToggle: () => void; collapsed: boolean; onNavigate?: () => void;
}) {
  const id = useId();
  const { item, children } = branch;
  if (collapsed || children.length === 0) {
    return (
      <>
        <li className="flex"><NavLink item={item} active={item.href === current} collapsed={collapsed} onNavigate={onNavigate} /></li>
        {collapsed && children.map((c) => (
          <li key={c.href} className="flex"><NavLink item={c} active={c.href === current} collapsed sub onNavigate={onNavigate} /></li>
        ))}
      </>
    );
  }
  return (
    <li>
      <div className="flex items-center gap-1">
        <NavLink item={item} active={item.href === current} collapsed={false} onNavigate={onNavigate} />
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls={id}
          className="grid size-8 shrink-0 place-items-center rounded-[var(--radius-control)] text-muted hover:bg-sand/60 hover:text-accent"
        >
          <Icon name="chevronDown" className={cn("size-4 transition-transform duration-200 motion-reduce:transition-none", open ? "rotate-0" : "-rotate-90")} />
          <span className="sr-only">{open ? `Hide ${item.label} pages` : `Show ${item.label} pages`}</span>
        </button>
      </div>
      <Collapse open={open} id={id}>
        <ul className="relative ml-5 mt-0.5 space-y-0.5 border-l border-line pl-2">
          {children.map((c) => (
            <li key={c.href} className="flex"><NavLink item={c} active={c.href === current} collapsed={false} sub onNavigate={onNavigate} /></li>
          ))}
        </ul>
      </Collapse>
    </li>
  );
}

function Section({ group, current, saved, toggle, collapsed, onNavigate, first }: {
  group: NavGroup & { items: NavItem[] }; current?: string; saved: Saved; toggle: (key: string, open: boolean) => void;
  collapsed: boolean; onNavigate?: () => void; first: boolean;
}) {
  const id = useId();
  const list = branches(group.items);
  const sectionKey = `g:${group.label ?? ""}`;
  const open = !group.label || collapsed || saved[sectionKey] !== false;
  const items = (
    <ul className="space-y-0.5">
      {list.map((b) => {
        const branchKey = `b:${b.item.href}`;
        const branchOpen = saved[branchKey] === true;
        return (
          <BranchItem key={b.item.href} branch={b} current={current} open={branchOpen} collapsed={collapsed}
            onToggle={() => toggle(branchKey, !branchOpen)} onNavigate={onNavigate} />
        );
      })}
    </ul>
  );

  return (
    <div className={first ? "" : collapsed ? "mt-2" : "mt-3"}>
      {group.label && (collapsed ? (
        <hr className="mx-2 mb-2 border-line" />
      ) : (
        <button
          type="button"
          onClick={() => toggle(sectionKey, !open)}
          aria-expanded={open}
          aria-controls={id}
          className="font-admin group flex w-full items-center justify-between rounded-[var(--radius-control)] px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted hover:text-ink"
        >
          <span>{group.label}</span>
          {!open && current && group.items.some((i) => i.href === current) && <span className="sr-only">(holds this page)</span>}
          <Icon name="chevronDown" className={cn("ml-auto size-3.5 transition-transform duration-200 motion-reduce:transition-none", open ? "rotate-0" : "-rotate-90")} />
        </button>
      ))}
      {group.label && !collapsed ? <Collapse open={open} id={id}>{items}</Collapse> : items}
    </div>
  );
}

export function NavAccordion({ groups, onNavigate, collapsed }: { groups: NavGroup[]; onNavigate?: () => void; collapsed: boolean }) {
  const { can } = useAuth();
  const pathname = usePathname();
  const current = activeHref(pathname, groups);
  const [saved, setSaved] = useState<Saved>({});
  useEffect(() => setSaved(readSaved()), []);
  // Arriving on a page opens the section and the branch it sits in (the rest stay as they were left).
  const groupsRef = useRef(groups);
  groupsRef.current = groups;
  useEffect(() => {
    if (!current) return;
    for (const g of groupsRef.current) {
      for (const b of branches(g.items)) {
        if (![b.item, ...b.children].some((i) => i.href === current)) continue;
        const keys = [`g:${g.label ?? ""}`, ...(b.children.length ? [`b:${b.item.href}`] : [])];
        setSaved((s) => {
          if (keys.every((k) => s[k] === true)) return s;
          const next = { ...s, ...Object.fromEntries(keys.map((k) => [k, true])) };
          writeSaved(next);
          return next;
        });
        return;
      }
    }
  }, [current]);
  const toggle = useCallback((key: string, open: boolean) => {
    setSaved((s) => {
      const next = { ...s, [key]: open };
      writeSaved(next);
      return next;
    });
  }, []);

  const visible = useMemo(() => groups
    .map((g) => ({ ...g, items: g.items.filter((i) => !i.hidden && (!i.permission || can(i.permission))) }))
    .filter((g) => g.items.length > 0), [groups, can]);

  return (
    <>
      {visible.map((group, gi) => (
        <Section key={group.label ?? gi} group={group} current={current} saved={saved} toggle={toggle}
          collapsed={collapsed} onNavigate={onNavigate} first={gi === 0} />
      ))}
    </>
  );
}
