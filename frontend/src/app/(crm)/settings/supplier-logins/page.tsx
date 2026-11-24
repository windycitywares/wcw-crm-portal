"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/client-api";
import { formatDateTime } from "@/lib/utils";
import { useSuppliers } from "@/modules/channels/SupplierFilter";

interface Login {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  last_login_at: string | null;
  account_id: number | null;
  supplier_name: string | null;
  channels: string[];
}
const CHANNELS = [{ key: "etsy", label: "Etsy" }];
const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

function LoginDialog({ login, open, onClose, onSaved }: { login: Login | null; open: boolean; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const suppliers = useSuppliers();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [account, setAccount] = useState("");
  const [channels, setChannels] = useState<string[]>(["etsy"]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setEmail(login?.email ?? ""); setName(login?.full_name ?? ""); setPassword("");
    setAccount(login?.account_id ? String(login.account_id) : ""); setChannels(login?.channels.length ? login.channels : ["etsy"]);
  }, [open, login]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (login) {
        await apiFetch(`/supplier-portal/logins/${login.id}`, { method: "PATCH", body: JSON.stringify({ account_id: Number(account), channels }) });
        toast.push({ title: "Supplier login saved", description: login.email });
      } else {
        await apiFetch("/supplier-portal/logins", { method: "POST", body: JSON.stringify({ email, full_name: name, password, account_id: Number(account), channels }) });
        toast.push({ title: "Supplier login added", description: `${email} can sign in now. Share the password with them privately.` });
      }
      onSaved();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save the supplier login", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={login ? "Edit supplier login" : "Add supplier login"} size="md"
      description="A supplier signs in to see only their own orders and payments — never your revenue, profit, other suppliers or buyers' email.">
      <form onSubmit={submit} className="grid grid-cols-[minmax(0,1fr)] gap-3">
        {!login && <>
          <Field label="Name">{(p) => <Input {...p} maxLength={120} required value={name} onChange={(e) => setName(e.target.value)} />}</Field>
          <Field label="Email">{(p) => <Input {...p} maxLength={254} autoComplete="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
          <Field label="Password" hint="At least 10 characters. They can change it after signing in.">
            {(p) => <Input {...p} type="password" required minLength={10} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
          </Field>
        </>}
        <Field label="Supplier" hint="A supplier account. The person is added as a contact there.">
          {(p) => (
            <Select {...p} required value={account} onChange={(e) => setAccount(e.target.value)}>
              <option value="">Choose a supplier</option>
              {suppliers.map((s) => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
            </Select>
          )}
        </Field>
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium">Sales channels they may see</legend>
          {CHANNELS.map((c) => (
            <label key={c.key} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={channels.includes(c.key)}
                onChange={(e) => setChannels(e.target.checked ? [...channels, c.key] : channels.filter((x) => x !== c.key))} />
              {c.label}
            </label>
          ))}
        </fieldset>
        <div className="flex justify-end gap-2">
          <Button type="button" size="sm" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" size="sm" disabled={busy || !account || !channels.length}>{busy ? "Saving…" : login ? "Save supplier login" : "Add supplier login"}</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function SupplierLoginsPage() {
  const [rows, setRows] = useState<Login[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Login | null>(null);
  const [open, setOpen] = useState(false);
  const load = useCallback(async () => {
    try { setRows(await apiFetch<Login[]>("/supplier-portal/logins")); setError(null); } catch (e) { setError(errorText(e)); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const columns: Column<Login>[] = [
    { key: "who", header: "Login", cell: (l) => <div className="min-w-0"><div className="font-medium">{l.full_name}</div><div className="truncate text-xs text-muted">{l.email}</div></div> },
    { key: "supplier", header: "Supplier", cell: (l) => l.supplier_name ?? <span className="text-xs text-danger">Not linked</span> },
    { key: "channels", header: "Sees", hide: "sm", cell: (l) => l.channels.map((c) => CHANNELS.find((x) => x.key === c)?.label ?? c).join(", ") || "—" },
    { key: "status", header: "Status", hide: "md", cell: (l) => <Badge variant={l.is_active ? "success" : "neutral"}>{l.is_active ? "Active" : "Off"}</Badge> },
    { key: "last", header: "Last signed in", hide: "lg", cell: (l) => (l.last_login_at ? formatDateTime(l.last_login_at) : "Never") },
    { key: "edit", header: <span className="sr-only">Edit</span>, align: "right", cell: (l) => <Button size="sm" variant="secondary" onClick={() => { setEditing(l); setOpen(true); }}>Edit</Button> },
  ];

  return (
    <>
      <PageHeader title="Supplier logins" description="Outside suppliers who sign in to the CRM's supplier portal. Turn a login off or reset its password under Users."
        actions={<Button size="sm" onClick={() => { setEditing(null); setOpen(true); }}>Add supplier login</Button>} />
      {error && <p role="alert" className="mb-3 text-sm text-danger">{error}</p>}
      <div className="relative">
        <DataTable columns={columns} rows={rows} rowKey={(l) => l.id} caption="Supplier logins" empty="No supplier logins yet." />
      </div>
      <LoginDialog login={editing} open={open} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); void load(); }} />
    </>
  );
}
