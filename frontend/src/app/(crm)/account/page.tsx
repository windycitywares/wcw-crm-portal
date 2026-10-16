"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { usersApi } from "@/modules/users/api";
import { useAuth, type TokenResponse } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { ROLE_LABEL } from "@/lib/types";

function Profile() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState({ full_name: user?.full_name ?? "", title: user?.title ?? "", phone: user?.phone ?? "" });
  const [busy, setBusy] = useState(false);
  if (!user) return null;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      setUser(await usersApi.updateMe({ full_name: form.full_name, title: form.title || null, phone: form.phone || null }));
      toast.push({ title: "Profile saved" });
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel>
      <PanelHeader title="Profile" description={`${user.email} · ${ROLE_LABEL[user.role]} access`} />
      <PanelBody>
        <form onSubmit={save} className="grid max-w-lg gap-4">
          <Field label="Full name">{(p) => <Input {...p} required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />}</Field>
          <Field label="Job title" hint="Shown next to your name on records.">
            {(p) => <Input {...p} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />}
          </Field>
          <Field label="Phone">{(p) => <Input {...p} type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />}</Field>
          <div>
            <Button type="submit" size="sm" disabled={busy || !form.full_name.trim()}>
              {busy ? "Saving…" : "Save profile"}
            </Button>
          </div>
        </form>
      </PanelBody>
    </Panel>
  );
}

function ChangePassword() {
  const { acceptToken } = useAuth();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await apiFetch<TokenResponse>("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      acceptToken(res);
      setCurrent("");
      setNext("");
      toast.push({ title: "Password changed", description: "Other devices have been signed out." });
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't change password", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel>
      <PanelHeader title="Password" description="Changing it signs you out everywhere else." />
      <PanelBody>
        <form onSubmit={save} className="grid max-w-lg gap-4">
          <Field label="Current password">
            {(p) => <Input {...p} type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />}
          </Field>
          <Field label="New password" hint="At least 10 characters.">
            {(p) => <Input {...p} type="password" autoComplete="new-password" required minLength={10} value={next} onChange={(e) => setNext(e.target.value)} />}
          </Field>
          <div>
            <Button type="submit" size="sm" disabled={busy || !current || next.length < 10}>
              {busy ? "Changing…" : "Change password"}
            </Button>
          </div>
        </form>
      </PanelBody>
    </Panel>
  );
}

export default function AccountPage() {
  return (
    <>
      <PageHeader title="Your account" />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Profile />
        <ChangePassword />
      </div>
    </>
  );
}
