"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { campaignsApi, type Template, type TemplateSummary } from "@/modules/campaigns/api";

const EMPTY = {
  name: "",
  subject: "",
  preheader: "",
  html: "<p>Hello {{ customer.first_name }},</p><p>Here is your message.</p>",
  text: "Hello {{ customer.first_name }},\n\nHere is your message.",
};

export default function CampaignTemplatesPage() {
  const { can } = useAuth();
  const [templates, setTemplates] = useState<Page<TemplateSummary> | null>(null);
  const [editing, setEditing] = useState<Template | null>(null);
  const [form, setForm] = useState<typeof EMPTY>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canEdit = can("campaigns:edit");

  const load = async () => {
    try {
      setTemplates(await campaignsApi.templates.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load templates");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const isDirty = useMemo(() => {
    if (!editing) return form.name || form.subject || form.html;
    return (
      form.name !== (editing.name ?? "") ||
      form.subject !== (editing.subject ?? "") ||
      form.preheader !== (editing.preheader ?? "") ||
      form.html !== (editing.html ?? "") ||
      form.text !== (editing.text ?? "")
    );
  }, [editing, form]);

  const resetForm = () => {
    setEditing(null);
    setForm(EMPTY);
    setError(null);
  };

  const openNew = () => {
    setEditing(null);
    setForm(EMPTY);
  };

  const openEdit = async (id: number) => {
    try {
      const template = await campaignsApi.templates.get(id);
      setEditing(template);
      setForm({
        name: template.name,
        subject: template.subject,
        preheader: template.preheader ?? "",
        html: template.html,
        text: template.text,
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the template");
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canEdit) return;
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        subject: form.subject.trim(),
        preheader: form.preheader.trim() || null,
        html: form.html.trim(),
        text: form.text.trim() || null,
      };

      if (editing) {
        await campaignsApi.templates.update(editing.id, payload);
      } else {
        await campaignsApi.templates.create(payload);
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the template");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    if (!canEdit || !confirm("Delete this email template?")) return;
    try {
      await campaignsApi.templates.remove(id);
      if (editing?.id === id) resetForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete the template");
    }
  };

  return (
    <>
      <PageHeader
        title="Campaign templates"
        description="Reusable email bodies, merge fields and test previews for each campaign."
        actions={
          canEdit ? (
            <Button size="sm" onClick={openNew}>
              New template
            </Button>
          ) : undefined
        }
      />

      {error && (
        <div className="mb-4 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel>
          <PanelHeader title="Templates" description="Saved versions, content and the last editor." />
          <PanelBody className="space-y-3">
            {templates?.items.length ? (
              templates.items.map((template) => (
                <div key={template.id} className="flex items-center justify-between gap-3 rounded border border-line bg-canvas px-3 py-3">
                  <button type="button" className="min-w-0 flex-1 text-left" onClick={() => void openEdit(template.id)}>
                    <div className="truncate font-medium text-ink">{template.name}</div>
                    <div className="truncate text-sm text-muted">{template.subject}</div>
                  </button>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-xs text-muted">v{template.version}</span>
                    {canEdit && (
                      <Button variant="secondary" size="sm" onClick={() => void remove(template.id)}>
                        Delete
                      </Button>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted">No templates yet.</p>
            )}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title={editing ? `Edit: ${editing.name}` : "New template"} description="The saved HTML and text versions are both kept in sync." />
          <PanelBody>
            <form onSubmit={submit} className="space-y-4">
              <Field label="Template name">
                {(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
              </Field>

              <Field label="Subject line">
                {(p) => <Input {...p} value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />}
              </Field>

              <Field label="Preheader" hint="Optional line shown under the subject in many inboxes.">
                {(p) => <Input {...p} value={form.preheader} onChange={(e) => setForm({ ...form, preheader: e.target.value })} />}
              </Field>

              <Field label="HTML body">
                {(p) => <Textarea {...p} value={form.html} onChange={(e) => setForm({ ...form, html: e.target.value })} className="min-h-[180px]" />}
              </Field>

              <Field label="Text body" hint="Optional. If blank, it is derived from the HTML on save.">
                {(p) => <Textarea {...p} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} className="min-h-[120px]" />}
              </Field>

              <div className="flex flex-wrap items-center gap-2">
                <Button type="submit" disabled={!canEdit || !form.name || !form.subject || !form.html || busy}>
                  {busy ? "Saving…" : editing ? "Save changes" : "Create template"}
                </Button>
                {isDirty && (
                  <Button variant="secondary" onClick={resetForm}>
                    Reset
                  </Button>
                )}
              </div>
            </form>
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}
