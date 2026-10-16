"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { errorText, settingsApi, type EmailSettings } from "@/modules/settings/api";

type Form = Omit<EmailSettings, "smtp_password_set"> & { smtp_password: string };

const PORT_FOR = { ssl: 465, starttls: 587, none: 25 } as const;

export default function EmailSettingsPage() {
  const { user, can } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState<Form | null>(null);
  const [passwordSet, setPasswordSet] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null);
  const allowed = can("settings:manage");

  useEffect(() => {
    if (!allowed) return;
    settingsApi
      .get<EmailSettings>("email")
      .then(({ values }) => {
        const { smtp_password_set, ...rest } = values;
        setPasswordSet(smtp_password_set);
        setForm({ ...rest, smtp_password: "" });
      })
      .catch((err) => toast.push({ tone: "danger", title: "Couldn't load email settings", description: errorText(err) }));
    setTestTo(user?.email ?? "");
  }, [allowed, toast, user?.email]);

  if (!allowed) return <PageHeader title="Email" description="Only admins can change email settings." />;
  if (!form) return <PageHeader title="Email" description="Loading…" />;

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm({ ...form, [key]: value });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      const { values } = await settingsApi.save<EmailSettings>("email", { ...form });
      setPasswordSet(values.smtp_password_set);
      setForm({ ...form, smtp_password: "" });
      toast.push({ title: "Email settings saved", description: form.enabled ? "Outgoing email is on." : "Outgoing email is off." });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await settingsApi.testEmail(testTo));
    } catch (err) {
      setTestResult({ ok: false, detail: errorText(err) });
    } finally {
      setTesting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Email"
        description="The mailbox the CRM sends from: password resets now, campaigns and ticket replies later. Emails wait in a queue until this is switched on."
        actions={form.enabled ? <Pill tone="success">On</Pill> : <Pill>Off</Pill>}
      />
      <form onSubmit={save} className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-2">
        {error && (
          <p role="alert" className="rounded-[var(--radius-control)] border border-danger/30 bg-danger/8 px-3 py-2 text-sm text-danger xl:col-span-2">
            {error}
          </p>
        )}
        <Panel>
          <PanelHeader title="Mail server (SMTP)" description="From your hosting's Email Accounts → Connect Devices page." />
          <PanelBody className="grid gap-4 sm:grid-cols-2">
            <Field label="SMTP host" className="sm:col-span-2" hint="e.g. mail.windycitywares.com">
              {(p) => <Input {...p} value={form.smtp_host} onChange={(e) => set("smtp_host", e.target.value)} autoComplete="off" />}
            </Field>
            <Field label="Security">
              {(p) => (
                <Select
                  {...p}
                  value={form.smtp_security}
                  onChange={(e) => {
                    const sec = e.target.value as Form["smtp_security"];
                    setForm({ ...form, smtp_security: sec, smtp_port: PORT_FOR[sec] });
                  }}
                >
                  <option value="ssl">SSL/TLS (port 465)</option>
                  <option value="starttls">STARTTLS (port 587)</option>
                  <option value="none">None (not recommended)</option>
                </Select>
              )}
            </Field>
            <Field label="Port">
              {(p) => <Input {...p} type="number" min={1} max={65535} value={form.smtp_port} onChange={(e) => set("smtp_port", Number(e.target.value))} />}
            </Field>
            <Field label="Username" hint="Usually the full mailbox address.">
              {(p) => <Input {...p} value={form.smtp_user} onChange={(e) => set("smtp_user", e.target.value)} autoComplete="off" />}
            </Field>
            <Field label="Password" hint={passwordSet ? "Saved and encrypted. Leave blank to keep it." : "Stored encrypted; never shown again."}>
              {(p) => (
                <Input
                  {...p}
                  type="password"
                  value={form.smtp_password}
                  onChange={(e) => set("smtp_password", e.target.value)}
                  autoComplete="new-password"
                  placeholder={passwordSet ? "••••••••" : ""}
                />
              )}
            </Field>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Sender and limits" />
          <PanelBody className="grid gap-4 sm:grid-cols-2">
            <Field label="From name">{(p) => <Input {...p} value={form.from_name} onChange={(e) => set("from_name", e.target.value)} />}</Field>
            <Field label="From address">
              {(p) => <Input {...p} type="email" value={form.from_address} onChange={(e) => set("from_address", e.target.value)} />}
            </Field>
            <Field label="Reply-to address" hint="Optional. Where replies go.">
              {(p) => <Input {...p} type="email" value={form.reply_to} onChange={(e) => set("reply_to", e.target.value)} />}
            </Field>
            <Field label="Postal address" hint="Required in campaign footers (CAN-SPAM).">
              {(p) => <Input {...p} value={form.footer_address} onChange={(e) => set("footer_address", e.target.value)} />}
            </Field>
            <Field label="Daily limit" hint="All emails, any rolling 24 hours. Check your host's limit.">
              {(p) => <Input {...p} type="number" min={1} value={form.daily_limit} onChange={(e) => set("daily_limit", Number(e.target.value))} />}
            </Field>
            <Field label="Per minute" hint="Pacing, so the host doesn't flag you.">
              {(p) => <Input {...p} type="number" min={1} max={600} value={form.per_minute} onChange={(e) => set("per_minute", Number(e.target.value))} />}
            </Field>
          </PanelBody>
        </Panel>

        <div className="flex flex-wrap items-center gap-4 xl:col-span-2">
          <label className="flex items-center gap-3 text-sm font-medium">
            <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={form.enabled} onChange={(e) => set("enabled", e.target.checked)} />
            Send email from the CRM
          </label>
          <Button type="submit" size="sm" disabled={busy}>
            {busy ? "Saving…" : "Save email settings"}
          </Button>
        </div>
      </form>

      <Panel className="mt-6">
        <PanelHeader title="Send a test email" description="Uses the saved settings (save first). Shows the mail server's answer if it fails." />
        <PanelBody className="flex flex-wrap items-end gap-3">
          <Field label="Send to" className="min-w-0 flex-1 sm:max-w-sm">
            {(p) => <Input {...p} type="email" value={testTo} onChange={(e) => setTestTo(e.target.value)} />}
          </Field>
          <Button size="sm" variant="secondary" onClick={() => void test()} disabled={testing || !testTo}>
            {testing ? "Sending…" : "Send test email"}
          </Button>
          {testResult && (
            <p role="status" className={`w-full text-sm ${testResult.ok ? "text-success" : "text-danger"}`}>
              {testResult.detail}
            </p>
          )}
        </PanelBody>
      </Panel>
    </>
  );
}
