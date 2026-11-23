"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { Segmented } from "@/components/ui/Segmented";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { STATE_BADGE, STATE_LABEL, urnsApi, type ReviewRow } from "@/modules/urns/api";
import { useSizes } from "@/modules/urns/useSupplierRecords";

type Tab = "open" | "unclear" | "approved" | "all";
const err = (e: unknown) => (e instanceof Error ? e.message : undefined);

/** Every variation of every urn in one table: what the CRM read from the variation names, to check and approve
 *  in one go. Unclear ones are never approved in bulk — they need a person to type the pieces. */
export default function ReviewPage() {
  const { can } = useAuth();
  const toast = useToast();
  const canEdit = can("channels:edit");
  const sizes = useSizes().filter((s) => s.active);
  const [tab, setTab] = useState<Tab>("open");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<ReviewRow> | null>(null);
  const [drafts, setDrafts] = useState<Record<number, Record<string, string>>>({});
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await urnsApi.review(tab, page));
      setDrafts({});
      setPicked(new Set());
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't load the variations", description: err(e) });
    }
  }, [tab, page, toast]);
  useEffect(() => { void load(); }, [load]);

  const draftFor = (r: ReviewRow) =>
    drafts[r.id] ?? Object.fromEntries(sizes.map((s) => [s.code, r.quantities[s.code] ? String(r.quantities[s.code]) : ""]));
  const quantities = (r: ReviewRow) =>
    Object.fromEntries(Object.entries(draftFor(r)).filter(([, q]) => Number(q) > 0).map(([c, q]) => [c, Number(q)]));

  const act = async (fn: () => Promise<unknown>, title: string, description?: string) => {
    setBusy(true);
    try {
      await fn();
      toast.push({ title, description });
      await load();
    } catch (e) {
      toast.push({ tone: "danger", title: "That didn't work", description: err(e) });
    } finally {
      setBusy(false);
    }
  };

  const rows = data?.items ?? [];
  const pickable = rows.filter((r) => r.state === "proposed");
  const allPicked = pickable.length > 0 && pickable.every((r) => picked.has(r.id));

  return (
    <div className="space-y-5">
      <PageHeader title="Check variations"
        description="What the CRM read from each Etsy variation name. Fix any that are wrong (type the pieces and Save), then approve the rest."
        back={{ href: "/channels/etsy/urns", label: "Urns" }}
        actions={canEdit ? (
          <Button size="sm" disabled={busy || !rows.some((r) => r.state === "proposed")}
            onClick={() => void act(() => urnsApi.approve({}), "Approved", "Every variation that was read clearly is approved.")}>
            Approve everything read clearly
          </Button>
        ) : undefined} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented label="Show" value={tab} onChange={(v) => { setTab(v as Tab); setPage(1); }}
          options={[{ value: "open", label: "To check" }, { value: "unclear", label: "Needs you" }, { value: "approved", label: "Approved" }, { value: "all", label: "All" }]} />
        {canEdit && picked.size > 0 && (
          <Button size="sm" disabled={busy}
            onClick={() => void act(() => urnsApi.approve({ variation_ids: [...picked] }), "Approved", `${picked.size} variations approved as read.`)}>
            Approve {picked.size} selected
          </Button>
        )}
      </div>

      <Panel>
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <caption className="sr-only">Variations to check</caption>
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                {canEdit && (
                  <th scope="col" className="px-4 py-2">
                    <input type="checkbox" aria-label="Select every variation read clearly on this page" checked={allPicked}
                      onChange={() => setPicked(allPicked ? new Set() : new Set(pickable.map((r) => r.id)))} />
                  </th>
                )}
                <th scope="col" className="px-2 py-2 font-semibold">Urn</th>
                <th scope="col" className="px-2 py-2 font-semibold">Etsy variation</th>
                {sizes.map((s) => <th key={s.code} scope="col" className="px-2 py-2 text-right font-semibold">{s.label}</th>)}
                <th scope="col" className="px-2 py-2 font-semibold">State</th>
                <th scope="col" className="px-2 py-2 font-semibold">SKU</th>
                {canEdit && <th scope="col" className="px-4 py-2"><span className="sr-only">Save</span></th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0">
                  {canEdit && (
                    <td className="px-4 py-2">
                      {r.state === "proposed" && (
                        <input type="checkbox" aria-label={`Select ${r.urn_name}: ${r.label}`} checked={picked.has(r.id)}
                          onChange={() => setPicked((p) => { const n = new Set(p); if (n.has(r.id)) n.delete(r.id); else n.add(r.id); return n; })} />
                      )}
                    </td>
                  )}
                  <td className="px-2 py-2">
                    <Link href={`/channels/etsy/urns/${r.urn_id}`} className="font-medium hover:text-accent-strong hover:underline">{r.urn_name}</Link>
                    <div className="text-xs text-muted">#{r.urn_id}{r.supplier_name ? ` · ${r.supplier_name}` : " · no supplier"}</div>
                  </td>
                  <td className="px-2 py-2">
                    {r.label}
                    {r.note && <div className="text-xs text-danger">{r.note}</div>}
                  </td>
                  {sizes.map((s) => (
                    <td key={s.code} className="px-2 py-2 text-right">
                      {canEdit ? (
                        <>
                          <label className="sr-only" htmlFor={`r-${r.id}-${s.code}`}>{s.label} pieces in {r.urn_name}, {r.label}</label>
                          <input id={`r-${r.id}-${s.code}`} type="number" min={0} max={500} inputMode="numeric"
                            className="num w-16 rounded-[var(--radius-control)] border border-line bg-surface px-2 py-1 text-right focus-visible:outline-2 focus-visible:outline-accent"
                            value={draftFor(r)[s.code] ?? ""}
                            onChange={(e) => setDrafts((d) => ({ ...d, [r.id]: { ...draftFor(r), [s.code]: e.target.value } }))} />
                        </>
                      ) : <span className="num">{r.quantities[s.code] ?? "—"}</span>}
                    </td>
                  ))}
                  <td className="px-2 py-2"><Badge variant={STATE_BADGE[r.state]}>{STATE_LABEL[r.state]}</Badge></td>
                  <td className="px-2 py-2 font-mono text-xs">{r.sku ?? <span className="font-sans text-muted">{r.supplier_id ? "After approval" : "Needs a supplier"}</span>}</td>
                  {canEdit && (
                    <td className="px-4 py-2 text-right">
                      {(drafts[r.id] !== undefined || r.state !== "approved") && (
                        <Button size="sm" variant={drafts[r.id] !== undefined ? "primary" : "secondary"}
                          disabled={busy || Object.keys(quantities(r)).length === 0}
                          onClick={() => void act(() => urnsApi.setVariation(r.urn_id, r.id, quantities(r)), "Variation approved", `${r.urn_name}: ${r.label}`)}>
                          {drafts[r.id] !== undefined ? "Save" : "Approve"}
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
              {data && rows.length === 0 && (
                <tr><td colSpan={sizes.length + 6} className="px-4 py-8 text-center text-muted">
                  {tab === "open" ? "Nothing to check — every variation is approved." : "Nothing here."}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>
      {data && data.total > data.page_size && <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
    </div>
  );
}
