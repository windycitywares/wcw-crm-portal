"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDate, formatDateTime } from "@/lib/utils";
import { errorText, settingsApi } from "@/modules/settings/api";
import { trashApi, type TrashCount, type TrashItem, type TrashPage } from "@/modules/trash/api";

/** Deleted records wait here, restorable, until they are removed for good after the retention period. */
export default function TrashPageView() {
  const { can } = useAuth();
  const toast = useToast();
  const allowed = can("trash:manage");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<TrashPage | null>(null);
  const [counts, setCounts] = useState<TrashCount[]>([]);
  const [busy, setBusy] = useState(false);
  const [purging, setPurging] = useState<TrashItem | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, c] = await Promise.all([trashApi.list(type, page), trashApi.summary()]);
      setData(p);
      setCounts(c);
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't load the Trash", description: errorText(err) });
    }
  }, [type, page, toast]);
  useEffect(() => { if (allowed) void load(); }, [allowed, load]);

  if (!allowed) return <PageHeader title="Trash" description="Only managers and admins can see deleted records." />;

  const restore = async (item: TrashItem) => {
    setBusy(true);
    try {
      await trashApi.restore(item.type, item.id);
      toast.push({ title: "Restored", description: `${item.label} “${item.title}” is back.` });
      await load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't restore", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  };

  const purge = async () => {
    if (!purging) return;
    setBusy(true);
    try {
      await trashApi.purge(purging.type, purging.id);
      toast.push({ title: "Deleted for good", description: `${purging.label} “${purging.title}”.` });
      setPurging(null);
      await load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't delete for good", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<TrashItem>[] = [
    { key: "title", header: "Record", cell: (r) => (
      <div className="min-w-0">
        <div className="truncate font-medium">{r.title}</div>
        <div className="text-xs text-muted">{r.label}</div>
      </div>
    ) },
    { key: "deleted", header: "Deleted", hide: "sm", cell: (r) => formatDateTime(r.deleted_at) },
    { key: "purge", header: "Removed for good", hide: "md", cell: (r) => formatDate(r.purge_after) },
    { key: "actions", header: <span className="sr-only">Actions</span>, align: "right", cell: (r) => (
      <div className="flex justify-end gap-1">
        <Button size="sm" variant="secondary" disabled={busy} onClick={() => void restore(r)}>Restore</Button>
        {can("data:delete") && <Button size="sm" variant="ghost" disabled={busy} onClick={() => setPurging(r)}>Delete for good</Button>}
      </div>
    ) },
  ];
  const total = counts.reduce((n, c) => n + c.count, 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Trash"
        description={data ? `Deleted records stay here for ${data.retention_days} days, then they are removed for good.` : "Loading…"} />
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Record type">
          {(p) => (
            <Select {...p} value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
              <option value="">Everything ({total})</option>
              {counts.map((c) => <option key={c.type} value={c.type}>{c.label} ({c.count})</option>)}
            </Select>
          )}
        </Field>
      </div>
      <div className="relative">
        <DataTable caption="Deleted records" columns={columns} rows={data?.items ?? null} rowKey={(r) => `${r.type}-${r.id}`}
          empty="The Trash is empty." loading={busy} />
      </div>
      {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
      {can("settings:manage") && data && <RetentionPanel days={data.retention_days} onSaved={load} />}
      <ConfirmDialog open={purging !== null} title="Delete for good?" confirmLabel="Delete for good" busy={busy}
        message={purging ? `${purging.label} “${purging.title}” and everything stored with it will be removed now. This can't be undone.` : ""}
        onConfirm={() => void purge()} onCancel={() => setPurging(null)} />
    </div>
  );
}

function RetentionPanel({ days, onSaved }: { days: number; onSaved: () => void }) {
  const toast = useToast();
  const [value, setValue] = useState(String(days));
  const [busy, setBusy] = useState(false);
  useEffect(() => setValue(String(days)), [days]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await settingsApi.save("trash", { retention_days: Number(value) });
      toast.push({ title: "Retention saved", description: `Deleted records are kept for ${value} days.` });
      onSaved();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title="How long to keep deleted records" description="After this many days the Trash empties itself." />
      <PanelBody>
        <form onSubmit={save} className="flex flex-wrap items-end gap-3">
          <Field label="Days in the Trash" hint="1 to 3650">
            {(p) => <Input {...p} type="number" min={1} max={3650} required value={value} onChange={(e) => setValue(e.target.value)} className="w-32" />}
          </Field>
          <Button type="submit" size="sm" disabled={busy}>{busy ? "Saving…" : "Save retention"}</Button>
        </form>
      </PanelBody>
    </Panel>
  );
}
