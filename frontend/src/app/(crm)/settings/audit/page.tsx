"use client";

import { useCallback, useEffect, useState } from "react";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { usersApi, type AuditEntry } from "@/modules/users/api";

const ACTIONS: Record<string, string> = {
  "auth.login": "Signed in",
  "auth.login_failed": "Failed sign-in",
  "auth.password_changed": "Changed own password",
  "auth.reset_requested": "Asked for a password reset",
  "auth.password_reset": "Reset password",
  "user.create": "Added a user",
  "user.update": "Changed a user",
  "user.update_profile": "Updated own profile",
  "user.password_set": "Set a user's password",
};

function describeChanges(changes: AuditEntry["changes"]) {
  if (!changes) return "";
  return Object.entries(changes)
    .filter(([, v]) => Array.isArray(v))
    .map(([k, v]) => {
      const [from, to] = v as unknown[];
      return `${k.replace(/_/g, " ")}: ${from ?? "—"} → ${to ?? "—"}`;
    })
    .join(" · ");
}

export default function AuditPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<AuditEntry> | null>(null);
  const [loading, setLoading] = useState(false);
  const allowed = can("audit:view");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await usersApi.audit({ action, page, page_size: 50 }));
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't load the audit log", description: err instanceof Error ? err.message : undefined });
    } finally {
      setLoading(false);
    }
  }, [action, page, toast]);

  useEffect(() => {
    if (allowed) void load();
  }, [load, allowed]);

  if (!allowed) return <PageHeader title="Audit log" description="You don't have access to the audit log." />;

  const columns: Column<AuditEntry>[] = [
    { key: "at", header: "When", cell: (a) => <span className="num whitespace-nowrap text-muted">{formatDateTime(a.at)}</span> },
    { key: "who", header: "Who", cell: (a) => a.actor_email ?? <span className="text-muted">System</span> },
    { key: "what", header: "What", cell: (a) => ACTIONS[a.action] ?? a.action },
    {
      key: "details",
      header: "Details",
      hide: "md",
      cell: (a) => <span className="text-muted">{describeChanges(a.changes) || (a.entity_type ? `${a.entity_type} #${a.entity_id}` : "")}</span>,
    },
    { key: "ip", header: "IP", hide: "lg", cell: (a) => <span className="num text-muted">{a.ip ?? ""}</span> },
  ];

  return (
    <>
      <PageHeader title="Audit log" description="Sign-ins and changes, newest first. Entries can't be edited or deleted." />
      <Panel>
        <div className="flex flex-wrap items-end gap-3 border-b border-line px-4 py-3">
          <Field label="Show">
            {(p) => (
              <Select
                {...p}
                value={action}
                onChange={(e) => {
                  setAction(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">Everything</option>
                <option value="auth.">Sign-ins and passwords</option>
                <option value="auth.login_failed">Failed sign-ins</option>
                <option value="user.">User changes</option>
              </Select>
            )}
          </Field>
        </div>
        <DataTable caption="Audit log" columns={columns} rows={data?.items ?? null} rowKey={(a) => a.id} loading={loading} empty="Nothing recorded yet." />
        {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
      </Panel>
    </>
  );
}
