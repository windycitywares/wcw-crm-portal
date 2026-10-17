"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { errorText } from "@/modules/settings/api";
import { ticketsApi, type CannedResponse, type CannedResponseInput } from "@/modules/tickets/api";

/** Add or edit one saved reply. Its text is dropped into the reply box on a ticket. */
function CannedDialog({ open, response, onClose, onSaved }: { open: boolean; response: CannedResponse | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [active, setActive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setTitle(response?.title ?? "");
    setBody(response?.body ?? "");
    setActive(response?.is_active ?? true);
    setError(null);
  }, [open, response]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return setError("Give the reply a name.");
    if (!body.trim()) return setError("Write the reply text.");
    setBusy(true);
    setError(null);
    const data: CannedResponseInput = { title: title.trim(), body: body.trim(), is_active: active };
    try {
      if (response) await ticketsApi.updateCanned(response.id, data);
      else await ticketsApi.createCanned(data);
      toast.push({ title: response ? "Saved reply updated" : "Saved reply added", description: data.title });
      onSaved();
      onClose();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!response) return;
    setBusy(true);
    try {
      await ticketsApi.removeCanned(response.id);
      toast.push({ title: "Saved reply deleted", description: response.title });
      setDeleting(false);
      onSaved();
      onClose();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't delete", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={response ? "Edit saved reply" : "New saved reply"}
        description="Staff can drop this into a ticket reply and edit it before sending."
        footer={
          <>
            {response && (
              <Button variant="ghost" size="sm" className="mr-auto text-danger" onClick={() => setDeleting(true)}>
                Delete
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" form="canned-form" size="sm" disabled={busy}>
              {busy ? "Saving…" : response ? "Save reply" : "Add reply"}
            </Button>
          </>
        }
      >
        <form id="canned-form" onSubmit={save} className="grid gap-4">
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <Field label="Name" hint="Shown in the picker, e.g. “Where is my parcel?”">
            {(p) => <Input {...p} required maxLength={120} autoFocus value={title} onChange={(e) => setTitle(e.target.value)} />}
          </Field>
          <Field label="Reply text">
            {(p) => <Textarea {...p} required rows={6} maxLength={20000} value={body} onChange={(e) => setBody(e.target.value)} />}
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={active} onChange={(e) => setActive(e.target.checked)} />
            Active — shown in the reply box
          </label>
        </form>
      </Modal>
      <ConfirmDialog
        open={deleting}
        title="Delete this saved reply?"
        message={`“${response?.title}” will no longer appear in the reply box.`}
        confirmLabel="Delete reply"
        tone="danger"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setDeleting(false)}
      />
    </>
  );
}

export default function CannedResponsesPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState<CannedResponse[] | null>(null);
  const [editing, setEditing] = useState<CannedResponse | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    ticketsApi
      .cannedResponses()
      .then(setRows)
      .catch((err) => {
        setRows([]);
        toast.push({ tone: "danger", title: "Couldn't load saved replies", description: errorText(err) });
      });
  }, [toast]);

  useEffect(() => {
    if (can("lookups:manage")) load();
  }, [load, can]);

  if (!can("lookups:manage")) return <PageHeader title="Canned responses" description="Only admins can change saved replies." />;

  async function toggle(row: CannedResponse) {
    try {
      await ticketsApi.updateCanned(row.id, { is_active: !row.is_active });
      toast.push({ title: row.is_active ? "Reply paused" : "Reply active" });
      load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't update", description: errorText(err) });
    }
  }

  const columns: Column<CannedResponse>[] = [
    {
      key: "title",
      header: "Name",
      cell: (r) => (
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{r.title}</span>
          {!r.is_active && <Pill>Paused</Pill>}
        </div>
      ),
    },
    { key: "body", header: "Reply text", hide: "sm", cell: (r) => <p className="line-clamp-2 max-w-md whitespace-pre-wrap text-muted">{r.body}</p> },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (r) => (
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => void toggle(r)}>
            {r.is_active ? "Pause" : "Activate"}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setEditing(r)}>
            Edit
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Canned responses"
        description="Saved replies staff can drop into the reply box on a ticket and edit before sending."
        actions={
          <Button size="sm" onClick={() => setAdding(true)}>
            New saved reply
          </Button>
        }
      />
      <Panel>
        <DataTable columns={columns} rows={rows} rowKey={(r) => r.id} caption="Canned responses" empty="No saved replies yet. Add one to reuse it in the reply box." />
      </Panel>
      <CannedDialog
        open={adding || editing !== null}
        response={editing}
        onClose={() => {
          setAdding(false);
          setEditing(null);
        }}
        onSaved={load}
      />
    </>
  );
}
