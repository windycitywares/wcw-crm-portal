"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { customersApi, type Customer } from "@/modules/customers/api";
import { campaignsApi, type AudienceMember, type TargetList } from "@/modules/campaigns/api";

const PAGE_SIZE = 25;

export default function AudienceMembersPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const { can } = useAuth();
  const canEdit = can("campaigns:edit");
  const [id, setId] = useState<number | null>(null);
  const [audience, setAudience] = useState<TargetList | null>(null);
  const [members, setMembers] = useState<Page<AudienceMember> | null>(null);
  const [customers, setCustomers] = useState<Page<Customer> | null>(null);
  const [memberQuery, setMemberQuery] = useState("");
  const [memberSearch, setMemberSearch] = useState("");
  const [memberPage, setMemberPage] = useState(1);
  const [customerQuery, setCustomerQuery] = useState("");
  const [customerSearch, setCustomerSearch] = useState("");
  const [customerPage, setCustomerPage] = useState(1);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const { id: routeId } = await params;
      const numericId = Number(routeId);
      if (!Number.isSafeInteger(numericId) || numericId < 1) {
        setError("This audience could not be found.");
        return;
      }
      setId(numericId);
      try {
        const row = await campaignsApi.lists.get(numericId);
        setAudience(row);
        if (row.kind !== "static") setError("Only static lists have editable members.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't load this audience");
      }
    })();
  }, [params]);

  useEffect(() => {
    if (id === null || audience?.kind !== "static") return;
    void campaignsApi.lists.members(id, memberPage, PAGE_SIZE, memberQuery || undefined)
      .then(setMembers)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Couldn't load list members"));
  }, [id, audience?.kind, memberPage, memberQuery, revision]);

  useEffect(() => {
    if (audience?.kind !== "static") return;
    void customersApi.list({ q: customerQuery || undefined, page: customerPage, page_size: PAGE_SIZE })
      .then(setCustomers)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Couldn't search customers"));
  }, [audience?.kind, customerQuery, customerPage]);

  const searchMembers = (e: React.FormEvent) => {
    e.preventDefault();
    setMemberPage(1);
    setMemberQuery(memberSearch.trim());
  };

  const searchCustomers = (e: React.FormEvent) => {
    e.preventDefault();
    setCustomerPage(1);
    setCustomerQuery(customerSearch.trim());
  };

  const toggleCustomer = (customerId: number, checked: boolean) => {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(customerId);
      else next.delete(customerId);
      return next;
    });
  };

  const addSelected = async () => {
    if (id === null || selected.size === 0 || selected.size > 500) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await campaignsApi.lists.addMembers(id, [...selected]);
      setMessage(`Added ${result.added}; ${result.already} already on the list; ${result.missing} unavailable.`);
      setSelected(new Set());
      setAudience(await campaignsApi.lists.get(id));
      setRevision((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add customers to this list");
    } finally {
      setBusy(false);
    }
  };

  const removeMember = async (customerId: number) => {
    if (id === null || !window.confirm("Remove this customer from the list?")) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await campaignsApi.lists.removeMember(id, customerId);
      setAudience(await campaignsApi.lists.get(id));
      setRevision((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't remove this customer");
    } finally {
      setBusy(false);
    }
  };

  if (!audience) {
    return <PageHeader title="Audience members" description={error ?? "Loading audience…"} back={{ href: "/campaigns/lists", label: "Audiences" }} />;
  }

  return (
    <>
      <PageHeader
        title={audience.name}
        description={`${audience.members.toLocaleString()} members · ${audience.reachable.toLocaleString()} reachable`}
        back={{ href: "/campaigns/lists", label: "Audiences" }}
        actions={<ButtonLink href="/campaigns/lists" variant="secondary" size="sm">All audiences</ButtonLink>}
      />

      {error && <div role="alert" className="mb-4 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</div>}
      {message && <div role="status" className="mb-4 rounded border border-success/40 bg-success/8 px-3 py-2 text-sm text-success">{message}</div>}

      {audience.kind !== "static" ? (
        <Panel><PanelBody className="flex items-center justify-between gap-4 py-5">
          <p className="text-sm text-muted">This is a live segment. Edit its rules to change who matches.</p>
          <Button variant="secondary" size="sm" onClick={() => router.push("/campaigns/lists")}>Back to audiences</Button>
        </PanelBody></Panel>
      ) : (
        <div className="grid items-start gap-6 xl:grid-cols-2">
          <Panel>
            <PanelHeader title="Current members" description="Search this list and remove customers." />
            <PanelBody className="p-0">
              <form onSubmit={searchMembers} className="flex gap-2 border-b border-line p-4">
                <Field label="Search members" className="min-w-0 flex-1">
                  {(p) => <Input {...p} value={memberSearch} onChange={(e) => setMemberSearch(e.target.value)} placeholder="Name, company, or email" />}
                </Field>
                <Button type="submit" variant="secondary" size="sm" className="mt-auto">Search</Button>
              </form>
              <ul className="divide-y divide-line px-4">
                {members?.items.map((member) => (
                  <li key={member.customer_id} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{member.full_name}{member.company ? ` · ${member.company}` : ""}</div>
                      <div className="truncate text-xs text-muted">{member.email ?? "No email address"} · {member.reachable ? "Reachable" : "Not reachable"}</div>
                    </div>
                    {canEdit && <Button variant="ghost" size="sm" className="text-danger" disabled={busy} onClick={() => void removeMember(member.customer_id)}>Remove</Button>}
                  </li>
                ))}
                {members?.items.length === 0 && <li className="py-6 text-center text-sm text-muted">No members match this search.</li>}
              </ul>
              {members && <Pagination page={members.page} pageSize={members.page_size} total={members.total} onPage={setMemberPage} />}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Add customers" description={`${selected.size} selected · up to 500 per update`} />
            <PanelBody className="p-0">
              <form onSubmit={searchCustomers} className="flex gap-2 border-b border-line p-4">
                <Field label="Search CRM customers" className="min-w-0 flex-1">
                  {(p) => <Input {...p} value={customerSearch} onChange={(e) => setCustomerSearch(e.target.value)} placeholder="Name, company, or email" />}
                </Field>
                <Button type="submit" variant="secondary" size="sm" className="mt-auto">Search</Button>
              </form>
              <ul className="divide-y divide-line px-4">
                {customers?.items.map((customer) => (
                  <li key={customer.id} className="flex items-center gap-3 py-3">
                    <input
                      aria-label={`Select ${customer.display_name}`}
                      type="checkbox"
                      checked={selected.has(customer.id)}
                      disabled={!canEdit || (!selected.has(customer.id) && selected.size >= 500)}
                      onChange={(e) => toggleCustomer(customer.id, e.target.checked)}
                      className="size-4 accent-[var(--color-accent)]"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{customer.display_name}{customer.company && customer.display_name !== customer.company ? ` · ${customer.company}` : ""}</div>
                      <div className="truncate text-xs text-muted">{customer.email ?? "No email address"}</div>
                    </div>
                    <span className="shrink-0 text-xs text-muted">{customer.marketing_consent ? "Consented" : "No consent"}</span>
                  </li>
                ))}
                {customers?.items.length === 0 && <li className="py-6 text-center text-sm text-muted">No customers found.</li>}
              </ul>
              {customers && <Pagination page={customers.page} pageSize={customers.page_size} total={customers.total} onPage={setCustomerPage} />}
              {canEdit && <div className="border-t border-line p-4">
                <Button size="sm" disabled={busy || selected.size === 0} onClick={() => void addSelected()}>
                  {busy ? "Updating…" : `Add ${selected.size} selected`}
                </Button>
              </div>}
            </PanelBody>
          </Panel>
        </div>
      )}
    </>
  );
}