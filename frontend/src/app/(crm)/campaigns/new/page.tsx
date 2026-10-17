"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import { campaignsApi, type TargetList, type TemplateSummary } from "@/modules/campaigns/api";

export default function NewCampaignPage() {
  const { can } = useAuth();
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [lists, setLists] = useState<TargetList[]>([]);
  const [form, setForm] = useState({ name: "", template_id: "", target_list_id: "", scheduled_at: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canEdit = can("campaigns:edit") || can("campaigns:send");

  useEffect(() => {
    void (async () => {
      try {
        const [tpls, listPage] = await Promise.all([campaignsApi.templates.list(1, 100), campaignsApi.lists.list(1, 100)]);
        setTemplates(tpls.items);
        setLists(listPage.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't load campaign options");
      }
    })();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canEdit || !form.template_id || !form.target_list_id || !form.name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const campaign = await campaignsApi.create({
        name: form.name.trim(),
        template_id: Number(form.template_id),
        target_list_id: Number(form.target_list_id),
      });

      if (form.scheduled_at) {
        await campaignsApi.schedule(campaign.id, new Date(form.scheduled_at).toISOString());
      }

      window.location.href = "/campaigns";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the campaign");
    } finally {
      setBusy(false);
    }
  };

  if (!canEdit) {
    return <PageHeader title="Create campaign" description="You do not have permission to create campaigns." />;
  }

  return (
    <>
      <PageHeader title="Create campaign" description="Choose the template, audience and optional schedule for the next send." back={{ href: "/campaigns", label: "Campaigns" }} />

      {error && <div className="mb-4 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</div>}

      <Panel>
        <PanelHeader title="Campaign details" description="A campaign starts as a draft until it is scheduled or sent." />
        <PanelBody>
          <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
            <Field label="Campaign name" className="md:col-span-2">
              {(p) => <Input {...p} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />}
            </Field>

            <Field label="Template">
              {(p) => (
                <Select {...p} value={form.template_id} onChange={(e) => setForm((f) => ({ ...f, template_id: e.target.value }))}>
                  <option value="">Select a template</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>{template.name}</option>
                  ))}
                </Select>
              )}
            </Field>

            <Field label="Audience">
              {(p) => (
                <Select {...p} value={form.target_list_id} onChange={(e) => setForm((f) => ({ ...f, target_list_id: e.target.value }))}>
                  <option value="">Select an audience</option>
                  {lists.map((list) => (
                    <option key={list.id} value={list.id}>{list.name}</option>
                  ))}
                </Select>
              )}
            </Field>

            <Field label="Schedule for" className="md:col-span-2" hint="Leave blank to keep it as a draft.">
              {(p) => (
                <Input
                  {...p}
                  type="datetime-local"
                  value={form.scheduled_at}
                  onChange={(e) => setForm((f) => ({ ...f, scheduled_at: e.target.value }))}
                />
              )}
            </Field>

            <div className="md:col-span-2 flex flex-wrap items-center gap-2">
              <Button type="submit" disabled={busy || !form.name || !form.template_id || !form.target_list_id}>
                {busy ? "Creating…" : "Create campaign"}
              </Button>
            </div>
          </form>
        </PanelBody>
      </Panel>
    </>
  );
}
