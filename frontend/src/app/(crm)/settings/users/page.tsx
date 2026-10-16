"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL, type Page, type Role, type User } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { usersApi, type UserFilters } from "@/modules/users/api";

const ROLES = Object.keys(ROLE_LABEL) as Role[];
const ROLE_HINT: Record<Role, string> = {
  admin: "Everything, including users and settings.",
  manager: "All business data, reports, types and pipelines; no system settings.",
  sales: "Customers, own leads and deals, own tasks.",
  support: "Customers, tickets and own tasks.",
  marketing: "Campaigns, templates, lists and reports.",
  read_only: "Can look at everything they're shown; changes nothing.",
};
const PAGE_SIZE = 25;

function errorText(err: unknown) {
  return err instanceof Error ? err.message : "Something went wrong";
}

function RoleSelect({
  value,
  onChange,
  ...rest
}: Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "value" | "onChange"> & { value: Role; onChange: (r: Role) => void }) {
  return (
    <Select {...rest} value={value} onChange={(e) => onChange(e.target.value as Role)}>
      {ROLES.map((r) => (
        <option key={r} value={r}>
          {ROLE_LABEL[r]}
        </option>
      ))}
    </Select>
  );
}

function AddUser({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const blank = { email: "", full_name: "", role: "sales" as Role, password: "", title: "" };
  const [form, setForm] = useState(blank);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await usersApi.create({ ...form, title: form.title || null });
      toast.push({ title: "User added", description: `${form.full_name} can now sign in.` });
      setForm(blank);
      onSaved();
      onClose();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a user"
      description="Share the temporary password with them privately; they can change it under Your account."
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="add-user" size="sm" disabled={busy}>
            {busy ? "Adding…" : "Add user"}
          </Button>
        </>
      }
    >
      <form id="add-user" onSubmit={save} className="grid gap-4">
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <Field label="Full name">{(p) => <Input {...p} required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />}</Field>
        <Field label="Email">{(p) => <Input {...p} type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}</Field>
        <Field label="Role" hint={ROLE_HINT[form.role]}>
          {(p) => <RoleSelect {...p} value={form.role} onChange={(role) => setForm({ ...form, role })} />}
        </Field>
        <Field label="Job title" hint="Optional.">
          {(p) => <Input {...p} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />}
        </Field>
        <Field label="Temporary password" hint="At least 10 characters.">
          {(p) => <Input {...p} type="text" autoComplete="off" required minLength={10} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />}
        </Field>
      </form>
    </Modal>
  );
}

function EditUser({ user, onClose, onSaved }: { user: User | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const { user: me } = useAuth();
  const [form, setForm] = useState({ full_name: "", title: "", phone: "", role: "sales" as Role, is_active: true });
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) setForm({ full_name: user.full_name, title: user.title ?? "", phone: user.phone ?? "", role: user.role, is_active: user.is_active });
    setPassword("");
    setError(null);
  }, [user]);

  if (!user) return null;
  const self = me?.id === user.id;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    setBusy(true);
    setError(null);
    try {
      await usersApi.update(user.id, { ...form, title: form.title || null, phone: form.phone || null });
      if (password) await usersApi.setPassword(user.id, password);
      toast.push({ title: "User saved", description: password ? "New password set; they must sign in again." : undefined });
      onSaved();
      onClose();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={user.full_name}
      description={user.email}
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="edit-user" size="sm" disabled={busy}>
            {busy ? "Saving…" : "Save user"}
          </Button>
        </>
      }
    >
      <form id="edit-user" onSubmit={save} className="grid gap-4">
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <Field label="Full name">{(p) => <Input {...p} required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />}</Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Job title">{(p) => <Input {...p} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />}</Field>
          <Field label="Phone">{(p) => <Input {...p} type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />}</Field>
        </div>
        <Field label="Role" hint={self ? "You can't change your own role." : ROLE_HINT[form.role]}>
          {(p) => <RoleSelect {...p} value={form.role} disabled={self} onChange={(role) => setForm({ ...form, role })} />}
        </Field>
        <label className="flex items-start gap-3 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-[var(--color-accent)]"
            checked={form.is_active}
            disabled={self}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
          />
          <span>
            <span className="font-medium">Active</span>
            <span className="block text-muted">Inactive users can&apos;t sign in. Their records and history stay.</span>
          </span>
        </label>
        <Field label="Set a new password" hint="Optional. At least 10 characters; signs them out everywhere.">
          {(p) => <Input {...p} type="text" autoComplete="off" minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
      </form>
    </Modal>
  );
}

export default function UsersPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [filters, setFilters] = useState<UserFilters>({ q: "", role: "", active: "true", page: 1 });
  const [data, setData] = useState<Page<User> | null>(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const allowed = can("users:manage");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await usersApi.list({ ...filters, page_size: PAGE_SIZE }));
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't load users", description: errorText(err) });
    } finally {
      setLoading(false);
    }
  }, [filters, toast]);

  useEffect(() => {
    if (!allowed) return;
    const t = window.setTimeout(load, filters.q ? 250 : 0);
    return () => window.clearTimeout(t);
  }, [load, allowed, filters.q]);

  if (!allowed) {
    return <PageHeader title="Users" description="Only admins can manage users." />;
  }

  const columns: Column<User>[] = [
    {
      key: "name",
      header: "Name",
      cell: (u) => (
        <button type="button" onClick={() => setEditing(u)} className="text-left">
          <span className="font-medium text-accent hover:underline">{u.full_name}</span>
          <span className="block text-xs text-muted">{u.email}</span>
        </button>
      ),
    },
    { key: "role", header: "Role", cell: (u) => ROLE_LABEL[u.role] },
    { key: "title", header: "Title", hide: "md", cell: (u) => u.title || <span className="text-muted">—</span> },
    {
      key: "status",
      header: "Status",
      cell: (u) => (u.is_active ? <Pill tone="success">Active</Pill> : <Pill>Inactive</Pill>),
    },
    { key: "last", header: "Last sign-in", hide: "lg", cell: (u) => <span className="num text-muted">{formatDateTime(u.last_login_at)}</span> },
  ];

  return (
    <>
      <PageHeader
        title="Users"
        description="Your team's CRM accounts and what each role can do."
        actions={
          <Button size="sm" onClick={() => setAdding(true)}>
            <Icon name="plus" className="size-4" />
            Add user
          </Button>
        }
      />
      <Panel>
        <div className="flex flex-wrap items-end gap-3 border-b border-line px-4 py-3">
          <Field label="Search" className="min-w-0 flex-1 sm:max-w-xs">
            {(p) => <Input {...p} type="search" placeholder="Name or email" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value, page: 1 })} />}
          </Field>
          <Field label="Role">
            {(p) => (
              <Select {...p} value={filters.role} onChange={(e) => setFilters({ ...filters, role: e.target.value as Role | "", page: 1 })}>
                <option value="">All roles</option>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABEL[r]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Status">
            {(p) => (
              <Select {...p} value={filters.active} onChange={(e) => setFilters({ ...filters, active: e.target.value as UserFilters["active"], page: 1 })}>
                <option value="true">Active</option>
                <option value="false">Inactive</option>
                <option value="">All</option>
              </Select>
            )}
          </Field>
        </div>
        <DataTable caption="Users" columns={columns} rows={data?.items ?? null} rowKey={(u) => u.id} loading={loading} empty="No users match these filters." />
        {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(page) => setFilters({ ...filters, page })} />}
      </Panel>
      <AddUser open={adding} onClose={() => setAdding(false)} onSaved={load} />
      <EditUser user={editing} onClose={() => setEditing(null)} onSaved={load} />
    </>
  );
}
