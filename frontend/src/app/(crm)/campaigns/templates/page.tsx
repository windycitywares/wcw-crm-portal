"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { customersApi, type Customer } from "@/modules/customers/api";
import { campaignsApi, type MergeField, type RenderedTemplate, type Template, type TemplateSummary } from "@/modules/campaigns/api";

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
  const [mergeFields, setMergeFields] = useState<MergeField[]>([]);
  const [previewCustomers, setPreviewCustomers] = useState<Customer[]>([]);
  const [editing, setEditing] = useState<Template | null>(null);
  const [form, setForm] = useState<typeof EMPTY>(EMPTY);
  const [previewCustomerId, setPreviewCustomerId] = useState<number | null>(null);
  const [preview, setPreview] = useState<RenderedTemplate | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [testRecipient, setTestRecipient] = useState("");
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [testBusy, setTestBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const htmlRef = useRef<HTMLTextAreaElement>(null);
  const canEdit = can("campaigns:edit");
  const canSend = can("campaigns:send");

  const load = async () => {
    try {
      setTemplates(await campaignsApi.templates.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load templates");
    }
  };

  useEffect(() => {
    void load();
    campaignsApi.mergeFields().then(setMergeFields).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : "Couldn't load merge fields");
    });
    customersApi.list({ page: 1, page_size: 25 }).then((result) => setPreviewCustomers(result.items)).catch(() => setPreviewCustomers([]));
  }, []);

  const isDirty = useMemo((): boolean => {
    if (!editing) return Boolean(form.name || form.subject || form.html);
    return (
      form.name !== (editing.name ?? "") ||
      form.subject !== (editing.subject ?? "") ||
      form.preheader !== (editing.preheader ?? "") ||
      form.html !== (editing.html ?? "") ||
      form.text !== (editing.text ?? "")
    );
  }, [editing, form]);

  useEffect(() => {
    if (!form.subject.trim() || !form.html.trim()) {
      setPreview(null);
      setPreviewError(null);
      setPreviewLoading(false);
      return;
    }

    let active = true;
    const timer = setTimeout(() => {
      setPreviewLoading(true);
      setPreviewError(null);
      void campaignsApi.templates.previewDraft({
        subject: form.subject,
        preheader: form.preheader || null,
        html: form.html,
        text: form.text || null,
        customer_id: previewCustomerId,
      }).then((result) => {
        if (active) setPreview(result);
      }).catch((err: unknown) => {
        if (active) {
          setPreview(null);
          setPreviewError(err instanceof Error ? err.message : "Couldn't render this preview");
        }
      }).finally(() => {
        if (active) setPreviewLoading(false);
      });
    }, 350);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [form.subject, form.preheader, form.html, form.text, previewCustomerId]);

  const resetForm = () => {
    setEditing(null);
    setForm(EMPTY);
    setPreview(null);
    setTestMessage(null);
    setError(null);
  };

  const openNew = () => {
    setEditing(null);
    setForm(EMPTY);
    setPreviewCustomerId(null);
    setTestMessage(null);
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
      setPreviewCustomerId(null);
      setTestMessage(null);
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

      const saved = editing
        ? await campaignsApi.templates.update(editing.id, payload)
        : await campaignsApi.templates.create(payload);
      setEditing(saved);
      setForm({
        name: saved.name,
        subject: saved.subject,
        preheader: saved.preheader ?? "",
        html: saved.html,
        text: saved.text,
      });
      setTestMessage("Template saved. You can send a test of this version.");
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

  const insertMergeField = (name: string) => {
    const textarea = htmlRef.current;
    if (!textarea) return;
    const token = `{{ ${name} }}`;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const next = `${form.html.slice(0, start)}${token}${form.html.slice(end)}`;
    setForm((current) => ({ ...current, html: next }));
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + token.length, start + token.length);
    });
  };

  const sendTest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing || !canSend || isDirty || !testRecipient.trim()) return;
    setTestBusy(true);
    setError(null);
    setTestMessage(null);
    try {
      const result = await campaignsApi.templates.test(editing.id, {
        to: testRecipient.trim(),
        customer_id: previewCustomerId,
      });
      setTestMessage(`Test queued for ${result.to} with subject “${result.subject}”.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't queue the test email");
    } finally {
      setTestBusy(false);
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
                {(p) => <Textarea {...p} ref={htmlRef} value={form.html} onChange={(e) => setForm({ ...form, html: e.target.value })} className="min-h-[180px] font-mono" />}
              </Field>

              <div className="rounded border border-line bg-canvas p-3">
                <h3 className="text-sm font-medium">Insert merge field</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {mergeFields.map((field) => (
                    <Button key={field.name} type="button" variant="secondary" size="sm" title={field.description} onClick={() => insertMergeField(field.name)}>
                      {field.name}
                    </Button>
                  ))}
                </div>
              </div>

              <Field label="Text body" hint="Optional. If blank, it is derived from the HTML on save.">
                {(p) => <Textarea {...p} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} className="min-h-[120px]" />}
              </Field>

              <div className="flex flex-wrap items-center gap-2">
                <Button type="submit" disabled={!canEdit || !form.name || !form.subject || !form.html || busy}>
                  {busy ? "Saving…" : editing ? "Save changes" : "Create template"}
                </Button>
                {isDirty && (
                  <Button type="button" variant="secondary" onClick={resetForm}>
                    Reset
                  </Button>
                )}
              </div>
            </form>
          </PanelBody>
        </Panel>
      </div>

      <Panel className="mt-6">
        <PanelHeader title="Live preview" description="Rendered by the campaign email sandbox, including the compliance footer." />
        <PanelBody>
          <div className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] sm:items-end">
            <Field label="Preview customer">
              {(p) => <select {...p} className="h-10 w-full rounded-lg border border-line bg-surface px-3 text-sm text-ink" value={previewCustomerId ?? ""} onChange={(e) => setPreviewCustomerId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Sample customer</option>
                {previewCustomers.map((customer) => <option key={customer.id} value={customer.id}>{customer.display_name}{customer.email ? ` · ${customer.email}` : ""}</option>)}
              </select>}
            </Field>
            <div aria-live="polite" className="text-sm text-muted">{previewLoading ? "Updating preview…" : preview ? `Subject: ${preview.subject}${preview.preheader ? ` · ${preview.preheader}` : ""}` : "Enter a subject and HTML body to preview."}</div>
          </div>
          {previewError && <div role="alert" className="mb-3 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{previewError}</div>}
          {preview && <iframe title="Rendered email preview" sandbox="" srcDoc={preview.html} className="h-[560px] w-full rounded border border-line bg-white" />}

          {editing && canSend && (
            <form onSubmit={sendTest} className="mt-5 grid gap-3 border-t border-line pt-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
              <Field label="Send test to" hint={isDirty ? "Save your edits before sending a test." : "The saved template version will be queued through the mail outbox."}>
                {(p) => <Input {...p} type="email" value={testRecipient} onChange={(e) => setTestRecipient(e.target.value)} placeholder="you@example.com" />}
              </Field>
              <Button type="submit" size="sm" disabled={isDirty || testBusy || !testRecipient.trim()}>
                {testBusy ? "Queueing…" : "Send test"}
              </Button>
            </form>
          )}
          {editing && !canSend && <p className="mt-4 border-t border-line pt-4 text-sm text-muted">You need campaign send permission to send a test email.</p>}
          {testMessage && <p role="status" className="mt-3 text-sm text-success">{testMessage}</p>}
        </PanelBody>
      </Panel>
    </>
  );
}
