"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { AccountDialog } from "@/modules/accounts/AccountDialog";
import { accountsApi, type Account } from "@/modules/accounts/api";
import { contactsApi, type Contact } from "@/modules/contacts/api";
import { NotesPanel } from "@/modules/records/NotesPanel";
import { AccountDeals } from "@/modules/sales/AccountDeals";
import { TagEditor } from "@/modules/records/TagEditor";
import { Timeline } from "@/modules/records/Timeline";
import { useLookups } from "@/modules/settings/useLookups";
import { suppliersApi, type Supplier } from "@/modules/suppliers/api";

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="mt-0.5 break-words text-sm text-ink">{children || <span className="text-muted">—</span>}</dd>
    </div>
  );
}

/** People at the account: add someone new, or move an existing contact here. */
function PeoplePanel({ account, canEdit, onChange }: { account: Account; canEdit: boolean; onChange: () => void }) {
  const toast = useToast();
  const [people, setPeople] = useState<Contact[] | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setPeople((await accountsApi.contacts(account.id)).items);
    } catch {
      setPeople([]);
    }
  }, [account.id]);
  useEffect(() => { void load(); }, [load, account.updated_at]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() && !email.trim()) return;
    setBusy(true);
    const [first, ...rest] = name.trim().split(/\s+/);
    try {
      const existing = email.trim() ? (await contactsApi.list({ q: email.trim(), page_size: 5 })).items
        .find((c) => c.email === email.trim().toLowerCase()) : undefined;
      if (existing) {
        await contactsApi.update(existing.id, { account_id: account.id });
        toast.push({ title: "Contact moved here", description: `${existing.display_name} is now at ${account.name}.` });
      } else {
        await contactsApi.create({ first_name: first || null, last_name: rest.join(" ") || null, email: email.trim() || null,
          title: title.trim() || null, company: account.name, account_id: account.id,
          types: [account.account_type === "supplier" ? "vendor" : account.account_type === "partner" ? "partner" : "other"] });
        toast.push({ title: "Contact added", description: `${name.trim() || email.trim()} at ${account.name}.` });
      }
      setName(""); setEmail(""); setTitle("");
      await load();
      onChange();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't add the contact", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  };

  const takeOff = async (c: Contact) => {
    setBusy(true);
    try {
      await contactsApi.update(c.id, { account_id: null });
      toast.push({ title: "Contact removed from account", description: `${c.display_name} stays in Contacts.` });
      await load();
      onChange();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't remove", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title="People" description="Contacts at this account." />
      <PanelBody className="space-y-4">
        <ul className="divide-y divide-line">
          {(people ?? []).map((c) => (
            <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 font-medium">
                  <Link href={`/contacts?q=${encodeURIComponent(c.email ?? c.display_name)}`} className="hover:text-accent-strong hover:underline">{c.display_name}</Link>
                  {account.primary_contact_id === c.id && <Badge variant="info">Primary</Badge>}
                </div>
                <div className="text-xs text-muted">{[c.title, c.email, c.phone].filter(Boolean).join(" · ") || "No contact details"}</div>
              </div>
              {canEdit && account.account_type !== "supplier" && (
                <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => void takeOff(c)}>Remove from account</Button>
              )}
            </li>
          ))}
          {people !== null && people.length === 0 && <li className="py-2 text-sm text-muted">Nobody recorded here yet.</li>}
          {people === null && <li className="py-2 text-sm text-muted">Loading…</li>}
        </ul>
        {canEdit && account.account_type !== "supplier" && (
          <form onSubmit={add} className="grid grid-cols-[minmax(0,1fr)] gap-3 border-t border-line pt-4 sm:grid-cols-3">
            <Field label="Name">{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
            <Field label="Email" hint="An existing contact with this email is moved here">{(p) => <Input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
            <Field label="Job title">{(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} />}</Field>
            <div className="sm:col-span-3">
              <Button type="submit" size="sm" disabled={busy || (!name.trim() && !email.trim())}>{busy ? "Adding…" : "Add contact"}</Button>
            </div>
          </form>
        )}
        {account.account_type === "supplier" && <p className="text-xs text-muted">A supplier&apos;s people are managed on its supplier page.</p>}
      </PanelBody>
    </Panel>
  );
}

export default function AccountPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const { can, user } = useAuth();
  const lookups = useLookups();
  const [account, setAccount] = useState<Account | null>(null);
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let alive = true;
    void accountsApi.get(Number(id)).then((a) => {
      if (!alive) return;
      setAccount(a);
      if (a.account_type === "supplier" && can("suppliers:view")) {
        void suppliersApi.forAccount(a.id).then((s) => alive && setSupplier(s)).catch(() => alive && setSupplier(null));
      }
    }).catch((e: unknown) => alive && setError(e instanceof Error ? e.message : "Couldn't load the account"));
    return () => { alive = false; };
  }, [id, refresh]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <><PageHeader title="Account" back={{ href: "/accounts", label: "Accounts" }} /><p role="alert" className="text-sm text-danger">{error}</p></>;
  if (!account) return <p className="text-sm text-muted">Loading…</p>;

  const canEdit = can("customers:edit_any") || (can("customers:edit_own") && account.owner_id === user?.id);
  const record = { type: "account", id: account.id };
  const changed = () => setRefresh((n) => n + 1);
  const isSupplier = account.account_type === "supplier";

  const archive = async () => {
    setBusy(true);
    try {
      await accountsApi.archive(account.id);
      toast.push({ title: "Account archived", description: account.name });
      router.push("/accounts");
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't archive", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
      setArchiving(false);
    }
  };

  return (
    <div>
      <PageHeader
        title={account.name}
        back={{ href: "/accounts", label: "Accounts" }}
        description={<span className="flex flex-wrap items-center gap-2">
          <Badge variant={isSupplier ? "warning" : "neutral"}>{lookups.find("account_type", account.account_type)?.label ?? account.account_type}</Badge>
          <Badge variant={account.status === "active" ? "success" : "neutral"}>{account.status === "active" ? "Active" : "Inactive"}</Badge>
          <span className="text-xs text-muted">Updated {formatDateTime(account.updated_at)}</span>
        </span>}
        actions={<div className="flex flex-wrap gap-2">
          {supplier && <ButtonLink href={`/suppliers/${supplier.id}`} size="sm" variant="secondary">Open supplier</ButtonLink>}
          {canEdit && !isSupplier && <Button size="sm" onClick={() => setEditing(true)}>Edit account</Button>}
          {can("customers:edit_any") && !isSupplier && <Button size="sm" variant="ghost" className="text-danger" onClick={() => setArchiving(true)}>Archive</Button>}
        </div>}
      />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="grid content-start gap-6">
          <Panel>
            <PanelHeader title="Details" description={isSupplier ? "Kept in step with the supplier record." : undefined} />
            <PanelBody>
              <dl className="grid grid-cols-2 gap-4">
                <Detail label="Industry">{account.industry}</Detail>
                <Detail label="Website">{account.website && <a href={account.website} target="_blank" rel="noreferrer" className="text-accent-strong hover:underline">{account.website}</a>}</Detail>
                <Detail label="Email">{account.email}</Detail>
                <Detail label="Phone">{account.phone}</Detail>
                <Detail label="City">{account.address?.city}</Detail>
                <Detail label="Country">{account.address?.country}</Detail>
              </dl>
              {account.notes && <p className="mt-4 whitespace-pre-wrap text-sm">{account.notes}</p>}
            </PanelBody>
          </Panel>
          <PeoplePanel account={account} canEdit={canEdit} onChange={changed} />
          <Panel>
            <PanelHeader title="Tags" />
            <PanelBody><TagEditor record={record} canEdit={canEdit} onChange={changed} /></PanelBody>
          </Panel>
        </div>
        <div className="grid content-start gap-6">
          {can("sales:view") && <AccountDeals accountId={account.id} accountName={account.name} onChange={changed} />}
          <NotesPanel record={record} onChange={changed} />
          <Timeline record={record} refreshKey={`${refresh}-${account.updated_at}`} />
        </div>
      </div>
      <AccountDialog open={editing} account={account} onClose={() => setEditing(false)}
        onSaved={(a) => { setEditing(false); setAccount(a); changed(); }} />
      <ConfirmDialog open={archiving} title="Archive account" confirmLabel="Archive account" busy={busy}
        message={`Archive ${account.name}? Its people stay in Contacts.`}
        onConfirm={() => void archive()} onCancel={() => setArchiving(false)} />
    </div>
  );
}
