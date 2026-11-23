"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { contactsApi, type Contact } from "@/modules/contacts/api";
import { useLookups } from "@/modules/settings/useLookups";
import { salesApi, type DealContact } from "./api";

/**
 * The buying committee: everyone on the deal and the part each plays (decision maker, signer, champion…), with
 * one main contact. Roles come from Settings → Types → Deal roles.
 */
export function DealPeoplePanel({ dealId, canEdit }: { dealId: number; canEdit: boolean }) {
  const toast = useToast();
  const lookups = useLookups();
  const roles = lookups.options("deal_role");
  const [people, setPeople] = useState<DealContact[] | null>(null);
  const [q, setQ] = useState("");
  const [matches, setMatches] = useState<Contact[]>([]);
  const [pick, setPick] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setPeople(await salesApi.dealContacts(dealId));
    } catch {
      setPeople([]);
    }
  }, [dealId]);
  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!canEdit || q.trim().length < 2) { setMatches([]); return; }
    let alive = true;
    const t = setTimeout(() => {
      contactsApi.list({ q: q.trim(), page_size: 10 }).then((p) => alive && setMatches(p.items)).catch(() => alive && setMatches([]));
    }, 250);
    return () => { alive = false; clearTimeout(t); };
  }, [q, canEdit]);

  const fail = (title: string) => (err: unknown) =>
    toast.push({ tone: "danger", title, description: err instanceof Error ? err.message : undefined });
  const label = (key: string | null) => (key ? lookups.find("deal_role", key)?.label ?? key : null);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pick) return;
    setBusy(true);
    try {
      const row = await salesApi.addDealContact(dealId, { contact_id: Number(pick), role: role || null,
        is_primary: (people ?? []).length === 0 });
      toast.push({ title: "Person added", description: `${row.contact_name}${row.role ? ` as ${label(row.role)}` : ""}.` });
      setPick(""); setQ(""); setRole("");
      await load();
    } catch (err) { fail("Couldn't add the person")(err); } finally { setBusy(false); }
  };

  const change = async (row: DealContact, data: { role?: string | null; is_primary?: boolean }, title: string) => {
    setBusy(true);
    try {
      await salesApi.updateDealContact(dealId, row.id, data);
      toast.push({ title, description: row.contact_name ?? undefined });
      await load();
    } catch (err) { fail("Couldn't save the change")(err); } finally { setBusy(false); }
  };

  const remove = async (row: DealContact) => {
    setBusy(true);
    try {
      await salesApi.removeDealContact(dealId, row.id);
      toast.push({ title: "Person removed", description: `${row.contact_name} is no longer on this deal.` });
      await load();
    } catch (err) { fail("Couldn't remove the person")(err); } finally { setBusy(false); }
  };

  return (
    <section aria-labelledby={`deal-people-${dealId}`} className="space-y-3">
      <div>
        <h3 id={`deal-people-${dealId}`} className="font-semibold">People on this deal</h3>
        <p className="text-sm text-muted">Who decides, who signs and who champions it.</p>
      </div>
      <ul className="divide-y divide-line">
        {(people ?? []).map((row) => (
          <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 font-medium">
                {row.contact_name}
                {row.is_primary && <Badge variant="info">Main contact</Badge>}
                {!canEdit && row.role && <span className="text-sm font-normal text-muted">{label(row.role)}</span>}
              </div>
              <div className="text-xs text-muted">{[row.title, row.email, row.phone].filter(Boolean).join(" · ")}</div>
            </div>
            {canEdit && (
              <div className="flex flex-wrap items-center gap-1">
                <label className="sr-only" htmlFor={`role-${row.id}`}>Role of {row.contact_name}</label>
                <Select id={`role-${row.id}`} value={row.role ?? ""} disabled={busy} className="w-44"
                  onChange={(e) => void change(row, { role: e.target.value || null }, "Role saved")}>
                  <option value="">No role</option>
                  {lookups.options("deal_role", row.role ?? undefined).map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
                </Select>
                {!row.is_primary && <Button type="button" size="sm" variant="ghost" disabled={busy}
                  onClick={() => void change(row, { is_primary: true }, "Main contact set")}>Make main contact</Button>}
                <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => void remove(row)}>Remove</Button>
              </div>
            )}
          </li>
        ))}
        {people !== null && people.length === 0 && <li className="py-2 text-sm text-muted">Nobody added yet.</li>}
      </ul>
      {canEdit && (
        <form onSubmit={add} className="grid grid-cols-[minmax(0,1fr)] items-end gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.8fr)_auto]">
          <Field label="Find a contact">{(p) => <Input {...p} type="search" placeholder="Name or email" value={q} onChange={(e) => setQ(e.target.value)} />}</Field>
          <Field label="Contact">
            {(p) => (
              <Select {...p} value={pick} onChange={(e) => setPick(e.target.value)}>
                <option value="">{q.trim().length < 2 ? "Type 2+ letters first" : matches.length ? "Choose…" : "No match"}</option>
                {matches.filter((m) => !(people ?? []).some((r) => r.contact_id === m.id))
                  .map((m) => <option key={m.id} value={m.id}>{m.display_name}{m.email ? ` (${m.email})` : ""}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Role">
            {(p) => (
              <Select {...p} value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="">No role</option>
                {roles.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
              </Select>
            )}
          </Field>
          <Button type="submit" size="sm" disabled={busy || !pick}>Add person</Button>
        </form>
      )}
    </section>
  );
}
