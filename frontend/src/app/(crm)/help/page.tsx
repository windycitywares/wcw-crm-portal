"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { groupedTopics, searchTopics, TOPICS } from "@/modules/help/content";
import { FLOWS } from "@/modules/help/flows";
import { FlowChart } from "@/modules/help/FlowChart";
import { Guide } from "@/modules/help/HelpPanel";
import { cn } from "@/lib/utils";

/** All the guides in one place: pick a page's guide to read it here, search across everything, or look at the flow charts at full size. */
export default function HelpCenter() {
  const [q, setQ] = useState("");
  const [id, setId] = useState<string | null>(null);
  const [view, setView] = useState<"guides" | "flows">("guides");

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("topic");
    if (t && TOPICS.some((x) => x.id === t)) setId(t);
  }, []);

  const select = (next: string | null) => {
    setId(next);
    setView("guides");
    window.history.replaceState(null, "", next ? `?topic=${next}` : window.location.pathname);
    window.scrollTo({ top: 0 });
  };

  const hits = useMemo(() => searchTopics(q), [q]);
  const searching = q.trim() !== "";
  const groups = useMemo(() => groupedTopics(), []);
  const topic = id ? TOPICS.find((t) => t.id === id) : undefined;

  return (
    <div>
      <PageHeader title="Help center" description="Plain-language guides for every page: what it is for, how to use it and where it fits. On any page, press ? to see its guide." />

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative w-full sm:max-w-sm">
          <label htmlFor="help-center-search" className="sr-only">Search all guides</label>
          <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <input id="help-center-search" type="search" autoComplete="off" maxLength={60} placeholder="Search all guides…" value={q} onChange={(e) => setQ(e.target.value)}
            className="h-9 w-full rounded-[var(--radius-control)] border border-line bg-surface pl-8 pr-3 text-sm placeholder:text-muted/80 hover:border-ink/40 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/25" />
        </div>
        <div role="group" aria-label="What to show" className="inline-flex rounded-[var(--radius-control)] border border-line p-0.5">
          {([["guides", "Guides"], ["flows", "Flow charts"]] as const).map(([k, label]) => (
            <button key={k} type="button" aria-pressed={view === k} onClick={() => setView(k)}
              className={cn("h-8 rounded-[calc(var(--radius-control)-2px)] px-3 text-sm font-medium", view === k ? "bg-accent text-white" : "text-ink hover:bg-sand")}>{label}</button>
          ))}
        </div>
      </div>

      {view === "flows" && !searching ? (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-2">
          {Object.values(FLOWS).map((f) => (
            <Panel key={f.id}>
              <PanelHeader title={f.title} />
              <PanelBody><FlowChart id={f.id} /></PanelBody>
            </Panel>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <nav aria-label="Guides" className="space-y-4">
            {searching ? (
              <div>
                <ul className="space-y-1">
                  {hits.map((t) => (
                    <li key={t.id}>
                      <button type="button" onClick={() => { setQ(""); select(t.id); }} className="w-full rounded-[var(--radius-control)] px-3 py-2 text-left hover:bg-sand">
                        <span className="block text-sm font-medium text-ink">{t.title}</span>
                        <span className="line-clamp-2 text-xs text-muted">{t.summary}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                {hits.length === 0 && <p className="px-3 py-2 text-sm text-muted">No guide matches “{q.trim()}”. Try a shorter word, like “sku” or “orders”.</p>}
              </div>
            ) : groups.map((g) => (
              <div key={g.label}>
                <h2 className="mb-1 px-3 text-xs font-semibold uppercase tracking-wide text-muted">{g.label}</h2>
                <ul>
                  {g.topics.map((t) => (
                    <li key={t.id}>
                      <button type="button" aria-current={t.id === id ? "page" : undefined} onClick={() => select(t.id)}
                        className={cn("w-full rounded-[var(--radius-control)] px-3 py-1.5 text-left text-sm hover:bg-sand", t.id === id ? "bg-sand font-medium text-ink" : "text-ink/85")}>
                        {t.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>

          <Panel>
            {topic ? (
              <>
                <PanelHeader title={topic.title} actions={<Link href={topic.href} className="text-sm text-accent hover:underline">Open this page</Link>} />
                <PanelBody><div className="max-w-2xl"><Guide topic={topic} onNavigate={() => {}} /></div></PanelBody>
              </>
            ) : (
              <PanelBody>
                <h2 className="text-lg font-semibold text-ink">Start here</h2>
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
                  Pick a guide from the list, or search for a word like “sku”, “ticket” or “campaign”. Each guide says what the page is for, how to use it, what its buttons and badges mean, and where it fits in the bigger picture.
                </p>
                <ul className="mt-4 list-disc space-y-1.5 pl-5 text-sm leading-relaxed">
                  <li>On any page, press <kbd className="rounded border border-line px-1.5 text-xs">?</kbd> or use the <strong>?</strong> in the top bar to see that page's guide.</li>
                  <li>An <strong>ⓘ</strong> beside a field's name explains that field.</li>
                  <li>Switch to <strong>Flow charts</strong> to see how the pages connect, from setting up to getting paid.</li>
                </ul>
              </PanelBody>
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}
