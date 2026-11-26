"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { searchTopics, topicFor, TOPICS } from "./content";
import { FlowChart } from "./FlowChart";
import type { HelpTopic } from "./types";

const Ctx = createContext<{ open: boolean; setOpen: (v: boolean) => void }>({ open: false, setOpen: () => {} });
export const useHelp = () => useContext(Ctx);

/** Holds whether the help panel is open, and opens it when "?" is pressed anywhere that isn't a text box. */
export function HelpProvider({ children, enabled = true }: { children: React.ReactNode; enabled?: boolean }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "?" || e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(input|textarea|select)$/i.test(t.tagName))) return;
      e.preventDefault();
      setOpen((o) => !o);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);
  const value = useMemo(() => ({ open, setOpen }), [open]);
  return <Ctx.Provider value={value}>{children}{enabled && <HelpPanel />}</Ctx.Provider>;
}

/** The round "?" in the top bar. */
export function HelpButton() {
  const { open, setOpen } = useHelp();
  return (
    <button type="button" onClick={() => setOpen(!open)} aria-haspopup="dialog" aria-expanded={open} title="Help for this page (?)"
      className="grid size-10 place-items-center rounded-full text-muted hover:bg-sand hover:text-ink">
      <Icon name="help" className="size-5" />
      <span className="sr-only">Help for this page</span>
    </button>
  );
}

function H({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wide text-muted">{children}</h3>;
}

function Guide({ topic, onNavigate }: { topic: HelpTopic; onNavigate: () => void }) {
  const { can } = useAuth();
  return (
    <div>
      <p className="text-sm leading-relaxed text-ink">{topic.summary}</p>

      {topic.steps && <>
        <H>How to use it</H>
        <ol className="list-decimal space-y-1.5 pl-5 text-sm leading-relaxed marker:font-semibold marker:text-accent">
          {topic.steps.map((s) => <li key={s}>{s}</li>)}
        </ol>
      </>}

      {topic.meanings && <>
        <H>What things mean</H>
        <dl className="space-y-2 text-sm">
          {topic.meanings.map((m) => (
            <div key={m.term} className="rounded-[var(--radius-control)] bg-canvas px-3 py-2">
              <dt className="font-semibold text-ink">{m.term}</dt>
              <dd className="text-muted">{m.text}</dd>
            </div>
          ))}
        </dl>
      </>}

      {topic.flow && <>
        <H>Where it fits</H>
        <FlowChart id={topic.flow.id} step={topic.flow.step} onNavigate={onNavigate} />
      </>}

      {topic.before && <>
        <H>Before you start</H>
        <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed">{topic.before.map((s) => <li key={s}>{s}</li>)}</ul>
      </>}

      {topic.affects && <>
        <H>What this affects</H>
        <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed">{topic.affects.map((s) => <li key={s}>{s}</li>)}</ul>
      </>}

      {topic.tips && <>
        <H>Tips and common questions</H>
        <div className="divide-y divide-line rounded-[var(--radius-control)] border border-line">
          {topic.tips.map((t) => (
            <details key={t.q} className="group px-3 py-2 text-sm">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 font-medium text-ink">
                {t.q}
                <Icon name="chevronDown" className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180" />
              </summary>
              <p className="mt-1.5 leading-relaxed text-muted">{t.a}</p>
            </details>
          ))}
        </div>
      </>}

      {topic.who && <>
        <H>Who can do what</H>
        <ul className="space-y-1.5 text-sm">
          {topic.who.map((w) => {
            const ok = can(w.permission);
            return (
              <li key={w.permission} className="flex items-start gap-2">
                <Icon name={ok ? "check" : "close"} className={cn("mt-0.5 size-4 shrink-0", ok ? "text-success" : "text-muted")} />
                <span className={ok ? "" : "text-muted"}>{w.text} <span className="text-xs">{ok ? "You can." : "You can't."}</span></span>
              </li>
            );
          })}
        </ul>
      </>}

      {topic.related && <>
        <H>Related pages</H>
        <ul className="flex flex-wrap gap-2">
          {topic.related.map((r) => (
            <li key={r.href}>
              <Link href={r.href} onClick={onNavigate} className="inline-flex items-center rounded-full border border-line px-3 py-1 text-sm hover:border-accent hover:text-accent">{r.label}</Link>
            </li>
          ))}
        </ul>
      </>}
    </div>
  );
}

function HelpPanel() {
  const { open, setOpen } = useHelp();
  const pathname = usePathname();
  const [q, setQ] = useState("");
  const [viewing, setViewing] = useState<HelpTopic | null>(null);
  useEffect(() => { setViewing(null); setQ(""); }, [pathname]);

  const here = topicFor(pathname);
  const topic = viewing ?? here;
  const hits = useMemo(() => searchTopics(q), [q]);
  const searching = q.trim() !== "";

  return (
    <Dialog.Root open={open} onOpenChange={setOpen} modal={false}>
      <Dialog.Portal>
        <Dialog.Content
          onInteractOutside={(e) => e.preventDefault()}
          onOpenAutoFocus={(e) => { e.preventDefault(); (e.currentTarget as HTMLElement).focus(); }}
          tabIndex={-1}
          className="fixed inset-y-0 right-0 z-[60] flex w-full flex-col bg-surface shadow-[var(--shadow-raised)] focus:outline-none sm:w-[26rem] sm:border-l sm:border-line">
          <div className="flex h-16 shrink-0 items-center justify-between gap-2 border-b border-line px-4">
            <Dialog.Title className="flex items-center gap-2 text-base font-semibold text-ink">
              <Icon name="help" className="size-5 text-accent" />
              Help
            </Dialog.Title>
            <Dialog.Close className="grid size-9 place-items-center rounded-full text-muted hover:bg-sand hover:text-ink">
              <Icon name="close" className="size-5" />
              <span className="sr-only">Close help</span>
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">Plain-language help for the page you are on, with search across all guides.</Dialog.Description>

          <div className="shrink-0 border-b border-line px-4 py-3">
            <label htmlFor="help-search" className="sr-only">Search help</label>
            <div className="relative">
              <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <input id="help-search" type="search" autoComplete="off" maxLength={60} placeholder="Search all help…" value={q} onChange={(e) => setQ(e.target.value)}
                className="h-9 w-full rounded-[var(--radius-control)] border border-line bg-surface pl-8 pr-3 text-sm placeholder:text-muted/80 hover:border-ink/40 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/25" />
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-8 pt-4">
            {searching ? (
              <div>
                <ul className="space-y-2">
                  {hits.map((t) => (
                    <li key={t.id}>
                      <button type="button" onClick={() => { setViewing(t); setQ(""); }}
                        className="w-full rounded-[var(--radius-control)] border border-line px-3 py-2 text-left hover:border-accent">
                        <span className="block text-sm font-medium text-ink">{t.title}</span>
                        <span className="line-clamp-2 text-xs text-muted">{t.summary}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                {hits.length === 0 && <p className="py-4 text-sm text-muted">No guide matches “{q.trim()}”. Try a shorter word, like “sku” or “orders”.</p>}
                <p role="status" className="sr-only">{hits.length} {hits.length === 1 ? "guide" : "guides"} found</p>
              </div>
            ) : topic ? (
              <div>
                {viewing && (
                  <button type="button" onClick={() => setViewing(null)} className="mb-3 inline-flex items-center gap-1 text-sm text-accent hover:underline">
                    <Icon name="chevronLeft" className="size-4" />
                    {here ? "Back to this page's help" : "Back"}
                  </button>
                )}
                <h2 className="text-lg font-semibold text-ink">{topic.title}</h2>
                {viewing && viewing.href !== pathname && (
                  <Link href={viewing.href} onClick={() => setViewing(null)} className="mt-1 inline-flex items-center gap-1 text-sm text-accent hover:underline">
                    Open this page <Icon name="chevronRight" className="size-4" />
                  </Link>
                )}
                <div className="mt-3"><Guide topic={topic} onNavigate={() => setViewing(null)} /></div>
              </div>
            ) : (
              <div className="text-sm leading-relaxed">
                <h2 className="text-lg font-semibold text-ink">No guide for this page yet</h2>
                <p className="mt-2 text-muted">Guides are being added page by page. In the meantime:</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  <li>Type in the box above to search the guides that exist.</li>
                  <li>Press <kbd className="rounded border border-line px-1.5 text-xs">/</kbd> to find any page by name in the menu.</li>
                  <li>Press <kbd className="rounded border border-line px-1.5 text-xs">?</kbd> on any page to open this help again.</li>
                </ul>
                <H>Pages with a guide</H>
                <ul className="space-y-1">
                  {TOPICS.map((t) => (
                    <li key={t.id}><button type="button" onClick={() => setViewing(t)} className="text-left text-accent hover:underline">{t.title}</button></li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
