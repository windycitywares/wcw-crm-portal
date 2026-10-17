"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { campaignsApi, type TargetList } from "@/modules/campaigns/api";

export default function CampaignListsPage() {
  const { can } = useAuth();
  const [data, setData] = useState<Page<TargetList> | null>(null);
  const [form, setForm] = useState({ name: "", description: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canEdit = can("campaigns:edit");

  const load = async () => {
    try {
      setData(await campaignsApi.lists.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load audiences");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canEdit || !form.name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await campaignsApi.lists.create({ name: form.name.trim(), description: form.description.trim() || null, kind: "static" });
      setForm({ name: "", description: "" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the audience");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    if (!canEdit || !confirm("Delete this audience?")) return;
    try {
      await campaignsApi.lists.remove(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete the audience");
    }
  };

  return (
    <>
      <PageHeader title="Campaign audiences" description="Static lists and segment-based audiences for each campaign." back={{ href: "/campaigns", label: "Campaigns" }} actions={canEdit ? undefined : undefined} />

      {error && <div className="mb-4 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</div>}

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Panel>
          <PanelHeader title="Existing audiences" description="A campaign copies the audience when it starts." />
          <PanelBody className="space-y-3">
            {data?.items.length ? (
              data.items.map((list) => (
                <div key={list.id} className="flex items-center justify-between gap-3 rounded border border-line bg-canvas px-3 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-ink">{list.name}</div>
                    <div className="text-sm text-muted">{list.kind} · {list.reachable} reachable / {list.members} members</div>
                  </div>
                  {canEdit && (
                    <Button variant="secondary" size="sm" onClick={() => void remove(list.id)}>
                      Delete
                    </Button>
                  )}
                </div>
              ))
            ) : (
              <p className="text-sm text-muted">No audiences created yet.</p>
            )}
          </PanelBody>
        </Panel>

        {canEdit && (
          <Panel>
            <PanelHeader title="New audience" description="Start with a static list; segments can be added later once the rule builder lands." />
            <PanelBody>
              <form onSubmit={submit} className="space-y-4">
                <Field label="Audience name">
                  {(p) => <Input {...p} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />}
                </Field>

                <Field label="Description" hint="Optional context for the team.">
                  {(p) => <Textarea {...p} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} className="min-h-[120px]" />}
                </Field>

                <Button type="submit" disabled={busy || !form.name.trim()}>
                  {busy ? "Creating…" : "Create audience"}
                </Button>
              </form>
            </PanelBody>
          </Panel>
        )}
      </div>
    </>
  );
}
