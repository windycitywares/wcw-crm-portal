"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDate, formatDateTime } from "@/lib/utils";
import { AccountDialog } from "@/modules/accounts/AccountDialog";
import { accountsApi, type Account, type AccountLink } from "@/modules/accounts/api";
import { GroupPanel } from "@/modules/accounts/GroupPanel";
import { contactsApi } from "@/modules/contacts/api";
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

/** "Mar 2024 – now" for a link's dates. */
function span(l: AccountLink) {
  const from = l.started_on ? formatDate(l.started_on) : "—";
  return l.ended_on ? `${from} – ${formatDate(l.ended_on)}` : `Since ${from}`;
}

/** People at the account: their role here and when. Someone can be at several accounts; one is their main one.
 *  Ending a link keeps it, so the account remembers who used to be there. */
function PeoplePanel({ account, canEdit, onChange }: { account: Account; canEdit: boolean; onChange: () => void }) {
  const toast = useToast();
  const [people, setPeople] = useState<AccountLink[] | null>(null);
  const [showPast, setShowPast] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [title, setTitle] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<AccountLink | null>(null);
  const [editRole, setEditRole] = useState("");
  const [ending, setEnding] = useState<AccountLink | null>(null);
  const supplier = account.account_type === "supplier";

  const load = useCallback(async () => {
    try {
      setPeople(await accountsApi.people(account.id, showPast));
    } catch {
      setPeople([]);
    }
  }, [account.id, showPast]);
  useEffect(() => { void load(); }, [load, account.updated_at]);

  const done = async () => { await load(); onChange(); };
  const fail = (title: string) => (err: unknown) =>
    toast.push({ tone: "danger", title, description: err instanceof Error ? err.message : undefined });

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() && !email.trim()) return;
    setBusy(true);
    const [first, ...rest] = name.trim().split(/\s+/);
    try {
      const existing = email.trim() ? (await contactsApi.list({ q: email.trim(), page_size: 5 })).items
        .find((c) => c.email === email.trim().toLowerCase()) : undefined;
      const contact = existing ?? await contactsApi.create({ first_name: first || null, last_name: rest.join(" ") || null,
        email: email.trim() || null, title: title.trim() || null, company: account.name,
        types: [account.account_type === "partner" ? "partner" : "other"] });
      await accountsApi.link(account.id, { contact_id: contact.id, role: role.trim() || null });
      toast.push({ title: existing ? "Contact linked" : "Contact added",
        description: `${contact.display_name} at ${account.name}${existing?.account_id ? " (their main account stays the same)" : ""}.` });
      setName(""); setEmail(""); setTitle(""); setRole("");
      await done();
    } catch (err) {
      fail("Couldn't add the contact")(err);
    } finally {
      setBusy(false);
    }
  };

  const makeMain = async (l: AccountLink) => {
    setBusy(true);
    try {
      await accountsApi.updateLink(l.id, { is_primary: true });
      toast.push({ title: "Main account changed", description: `${account.name} is now ${l.contact_name}'s main account.` });
      await done();
    } catch (err) { fail("Couldn't change the main account")(err); } finally { setBusy(false); }
  };

  const saveRole = async () => {
    if (!editing) return;
    setBusy(true);
    try {
      await accountsApi.updateLink(editing.id, { role: editRole.trim() || null });
      toast.push({ title: "Role saved", description: `${editing.contact_name}: ${editRole.trim() || "no role"}.` });
      setEditing(null);
      await done();
    } catch (err) { fail("Couldn't save the role")(err); } finally { setBusy(false); }
  };

  const end = async () => {
    if (!ending) return;
    setBusy(true);
    try {
      await accountsApi.endLink(ending.id);
      toast.push({ title: "Link ended", description: `${ending.contact_name} is kept as a past contact of ${account.name}.` });
      setEnding(null);
      await done();
    } catch (err) { fail("Couldn't end the link")(err); } finally { setBusy(false); }
  };

  return (
    <Panel>
      <PanelHeader title="People" description="Who is at this account, their role here and since when."
        actions={<label className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={showPast} onChange={(e) => setShowPast(e.target.checked)} />Show past people</label>} />
      <PanelBody className="space-y-4">
        <ul className="divide-y divide-line">
          {(people ?? []).map((l) => (
            <li key={l.id} className={`flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 ${l.active ? "" : "opacity-70"}`}>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 font-medium">
                  <Link href={`/contacts?q=${encodeURIComponent(l.email ?? l.contact_name ?? "")}`} className="hover:text-accent-strong hover:underline">{l.contact_name}</Link>
                  {l.role && <span className="text-sm font-normal text-muted">{l.role}</span>}
                  {account.primary_contact_id === l.contact_id && l.active && <Badge variant="info">Primary contact</Badge>}
                  {l.active && !l.is_primary && <Badge>Main account elsewhere</Badge>}
                  {!l.active && <Badge variant="warning">Left</Badge>}
                </div>
                <div className="text-xs text-muted">{[l.title, l.email, l.phone, span(l)].filter(Boolean).join(" · ")}</div>
              </div>
              {canEdit && !supplier && l.active && (
                <div className="flex flex-wrap gap-1">
                  <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => { setEditing(l); setEditRole(l.role ?? ""); }}>Edit role</Button>
                  {!l.is_primary && <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => void makeMain(l)}>Make main account</Button>}
                  <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => setEnding(l)}>End link</Button>
                </div>
              )}
            </li>
          ))}
          {people !== null && people.length === 0 && <li className="py-2 text-sm text-muted">Nobody recorded here yet.</li>}
          {people === null && <li className="py-2 text-sm text-muted">Loading…</li>}
        </ul>
        {canEdit && !supplier && (
          <form onSubmit={add} className="grid grid-cols-[minmax(0,1fr)] gap-3 border-t border-line pt-4 sm:grid-cols-2">
            <Field label="Name">{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
            <Field label="Email" hint="An existing contact with this email is linked here too">{(p) => <Input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
            <Field label="Job title">{(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} />}</Field>
            <Field label="Role at this account" hint="E.g. Buyer, Accounts payable, Advisor">{(p) => <Input {...p} value={role} maxLength={80} onChange={(e) => setRole(e.target.value)} />}</Field>
            <div className="sm:col-span-2">
              <Button type="submit" size="sm" disabled={busy || (!name.trim() && !email.trim())}>{busy ? "Adding…" : "Add contact"}</Button>
            </div>
          </form>
        )}
        {supplier && <p className="text-xs text-muted">A supplier&apos;s people are managed on its supplier page.</p>}
      </PanelBody>
      <Modal open={editing !== null} onClose={() => setEditing(null)} title="Edit role" size="sm"
        description={editing ? `${editing.contact_name} at ${account.name}` : undefined}
        footer={<><Button variant="secondary" onClick={() => setEditing(null)} disabled={busy}>Cancel</Button>
          <Button onClick={() => void saveRole()} disabled={busy}>{busy ? "Saving…" : "Save role"}</Button></>}>
        <Field label="Role at this account">{(p) => <Input {...p} value={editRole} maxLength={80} onChange={(e) => setEditRole(e.target.value)} />}</Field>
      </Modal>
      <ConfirmDialog open={ending !== null} title="End this link?" confirmLabel="End link" busy={busy}
        message={ending ? `${ending.contact_name} will be shown as a past contact of ${account.name} from today. The contact itself stays.` : ""}
        onConfirm={() => void end()} onCancel={() => setEnding(null)} />
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
          {account.parent_id && <span className="text-xs text-muted">Part of <Link href={`/accounts/${account.parent_id}`} className="text-accent-strong hover:underline">{account.parent_name}</Link></span>}
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
          <GroupPanel account={account} />
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
        message={`Move ${account.name} to the Trash? It can be restored from Settings → Trash. Its people stay in Contacts.`}
        onConfirm={() => void archive()} onCancel={() => setArchiving(false)} />
    </div>
  );
}
