"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { campaignsApi, type Suppression, type SuppressionReason } from "@/modules/campaigns/api";

const PAGE_SIZE = 25;
const REASONS: { value: SuppressionReason; label: string }[] = [
  { value: "unsubscribed", label: "Unsubscribed" },
  { value: "bounced", label: "Bounced" },
  { value: "complained", label: "Complaint" },
  { value: "manual", label: "Manual" },
];

export default function CampaignSuppressionsPage() {
  const { can } = useAuth();
  const canEdit = can("campaigns:edit");
  const [data, setData] = useState<Page<Suppression> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [reasonFilter, setReasonFilter] = useState<"" | SuppressionReason>("");
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState<SuppressionReason>("manual");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void campaignsApi.suppressions.list(page, PAGE_SIZE, reasonFilter || undefined, query || undefined)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Couldn't load suppressions");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [page, reasonFilter, query, revision]);

  const searchRows = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setQuery(search.trim());
  };

  const addSuppression = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canEdit || !email.trim()) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const created = await campaignsApi.suppressions.add({ email: email.trim(), reason, note: note.trim() || null });
      setEmail("");
      setNote("");
      setReason("manual");
      setMessage(`${created.email} added to the suppression list.`);
      setPage(1);
      setQuery("");
      setSearch("");
      setReasonFilter("");
      setRevision((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add this address");
    } finally {
      setBusy(false);
    }
  };

  const release = async (row: Suppression) => {
    if (!canEdit || !window.confirm(`Release ${row.email} from the suppression list?`)) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await campaignsApi.suppressions.release(row.id);
      setMessage(`${row.email} released from the suppression list.`);
      if (data?.items.length === 1 && page > 1) setPage((current) => current - 1);
      else setRevision((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't release this address");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Suppression list" description="Addresses excluded from campaign delivery." back={{ href: "/campaigns", label: "Campaigns" }} />

      {error && <div role="alert" className="mb-4 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</div>}
      {message && <div role="status" className="mb-4 rounded border border-success/40 bg-success/8 px-3 py-2 text-sm text-success">{message}</div>}

      <div className="grid items-start gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel>
          <PanelHeader title="Suppressed addresses" description={data ? `${data.total.toLocaleString()} active ${data.total === 1 ? "address" : "addresses"}` : "Campaigns will skip these addresses."} />
          <PanelBody className="p-0">
            <form onSubmit={searchRows} className="grid gap-3 border-b border-line p-4 sm:grid-cols-[minmax(0,1fr)_180px_auto] sm:items-end">
              <Field label="Search email or note">
                {(p) => <Input {...p} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Email address or note" />}
              </Field>
              <Field label="Reason">
                {(p) => <select {...p} className="h-10 w-full rounded-lg border border-line bg-surface px-3 text-sm text-ink" value={reasonFilter} onChange={(e) => { setReasonFilter(e.target.value as "" | SuppressionReason); setPage(1); }}>
                  <option value="">All reasons</option>
                  {REASONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>}
              </Field>
              <Button type="submit" size="sm" variant="secondary">Search</Button>
            </form>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-line bg-canvas text-xs uppercase text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">Address</th>
                    <th className="px-4 py-3 font-medium">Reason</th>
                    <th className="px-4 py-3 font-medium">Source</th>
                    <th className="px-4 py-3 font-medium">Added</th>
                    {canEdit && <th className="px-4 py-3" aria-label="Actions" />}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data?.items.map((row) => (
                    <tr key={row.id}>
                      <td className="max-w-[280px] px-4 py-3">
                        <div className="truncate font-medium text-ink">{row.email}</div>
                        {row.note && <div className="mt-0.5 truncate text-xs text-muted">{row.note}</div>}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-muted">{REASONS.find((item) => item.value === row.reason)?.label ?? row.reason}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-muted">{row.source ?? "—"}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-muted">{formatDateTime(row.created_at)}</td>
                      {canEdit && <td className="whitespace-nowrap px-4 py-3 text-right">
                        <Button type="button" variant="ghost" size="sm" className="text-danger" disabled={busy} onClick={() => void release(row)}>Release</Button>
                      </td>}
                    </tr>
                  ))}
                  {!loading && data?.items.length === 0 && <tr><td colSpan={canEdit ? 5 : 4} className="px-4 py-8 text-center text-muted">No suppressed addresses found.</td></tr>}
                  {loading && <tr><td colSpan={canEdit ? 5 : 4} className="px-4 py-8 text-center text-muted">Loading…</td></tr>}
                </tbody>
              </table>
            </div>
            {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
          </PanelBody>
        </Panel>

        {canEdit && <Panel>
          <PanelHeader title="Suppress an address" description="Manual suppressions are audited and can be released later." />
          <PanelBody>
            <form onSubmit={addSuppression} className="space-y-4">
              <Field label="Email address">
                {(p) => <Input {...p} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="person@example.com" />}
              </Field>
              <Field label="Reason">
                {(p) => <select {...p} className="h-10 w-full rounded-lg border border-line bg-surface px-3 text-sm text-ink" value={reason} onChange={(e) => setReason(e.target.value as SuppressionReason)}>
                  {REASONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>}
              </Field>
              <Field label="Note" hint="Optional context for the team.">
                {(p) => <Textarea {...p} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}
              </Field>
              <Button type="submit" size="sm" disabled={busy || !email.trim()}>{busy ? "Saving…" : "Add suppression"}</Button>
            </form>
          </PanelBody>
        </Panel>}
      </div>
    </>
  );
}