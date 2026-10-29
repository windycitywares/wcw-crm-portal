"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { IconButton, RowActions } from "@/components/ui/IconButton";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/utils";
import { inboxApi, type Mailbox } from "@/modules/inbox/api";
import { MailboxDialog } from "@/modules/inbox/MailboxDialog";
import { errorText } from "@/modules/settings/api";

/** Settings → Email accounts: the support mailboxes whose unread mail becomes tickets. */
export default function EmailAccountsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState<Mailbox[] | null>(null);
  const [editing, setEditing] = useState<Mailbox | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    inboxApi
      .list()
      .then(setRows)
      .catch((err) => {
        setRows([]);
        toast.push({ tone: "danger", title: "Couldn't load mailboxes", description: errorText(err) });
      });
  }, [toast]);

  useEffect(() => {
    if (can("inbox:manage")) load();
  }, [load, can]);

  if (!can("inbox:manage")) return <PageHeader title="Email accounts" description="Only admins can set up the mailboxes the CRM reads." />;

  async function toggle(row: Mailbox) {
    try {
      await inboxApi.update(row.id, { is_active: !row.is_active });
      toast.push({ title: row.is_active ? "Mailbox paused" : "Mailbox read again" });
      load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't update", description: errorText(err) });
    }
  }

  const columns: Column<Mailbox>[] = [
    {
      key: "address",
      header: "Mailbox",
      cell: (m) => (
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{m.address}</span>
            {!m.is_active && <Pill>Paused</Pill>}
          </p>
          {m.display_name && <p className="mt-0.5 text-xs text-muted">{m.display_name}</p>}
        </div>
      ),
    },
    {
      key: "server",
      header: "Server",
      hide: "md",
      cell: (m) => (
        <span className="text-muted">
          {m.imap_host}
          <span className="num"> :{m.imap_port}</span> · {m.folder}
        </span>
      ),
    },
    {
      key: "last",
      header: "Last read",
      hide: "sm",
      cell: (m) =>
        m.last_polled_at ? (
          <span className={m.last_error ? "text-danger" : "text-muted"} title={m.last_error ?? undefined}>
            {m.last_error ? "Failed " : ""}
            {timeAgo(m.last_polled_at)}
          </span>
        ) : (
          <span className="text-muted">Not read yet</span>
        ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (m) => (
        <RowActions>
          <IconButton icon={m.is_active ? "pause" : "play"} label={m.is_active ? `Pause ${m.address}` : `Resume ${m.address}`} onClick={() => void toggle(m)} />
          <IconButton icon="edit" label={`Edit ${m.address}`} onClick={() => setEditing(m)} />
        </RowActions>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Email accounts"
        description="The support mailboxes the CRM reads. Unread mail becomes tickets; replies go out from the address in Email settings."
        actions={
          <Button size="sm" onClick={() => setAdding(true)}>
            Add mailbox
          </Button>
        }
      />
      <Panel>
        <DataTable columns={columns} rows={rows} rowKey={(m) => m.id} caption="Mailboxes" empty="No mailboxes yet. Add one and its unread mail starts arriving as tickets." />
      </Panel>
      <MailboxDialog
        open={adding || editing !== null}
        mailbox={editing}
        onClose={() => {
          setAdding(false);
          setEditing(null);
        }}
        onSaved={load}
      />
    </>
  );
}
