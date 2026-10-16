"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { ConfirmDialog } from "@/components/ui/Modal";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { recordsApi, type Note, type RecordRef } from "./api";
import { useDirectory } from "./useDirectory";

/** Notes on any record. Anyone who can see the record can add one; authors (and managers) edit theirs. */
export function NotesPanel({ record, onChange }: { record: RecordRef; onChange?: () => void }) {
  const { user, can } = useAuth();
  const { name } = useDirectory();
  const toast = useToast();
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<{ id: number; body: string } | null>(null);
  const [deleting, setDeleting] = useState<Note | null>(null);
  const [busy, setBusy] = useState(false);
  const canTidy = can("data:export"); // managers/admins may edit anyone's notes

  const load = useCallback(async () => {
    try {
      setNotes(await recordsApi.notes(record));
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't load notes", description: err instanceof Error ? err.message : undefined });
    }
  }, [record.type, record.id, toast]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void load();
  }, [load]);

  async function run(action: () => Promise<unknown>, title: string) {
    setBusy(true);
    try {
      await action();
      toast.push({ title });
      await load();
      onChange?.();
      return true;
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save", description: err instanceof Error ? err.message : undefined });
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel>
      <PanelHeader title="Notes" />
      <form
        className="grid gap-2 border-b border-line px-5 py-4"
        onSubmit={async (e) => {
          e.preventDefault();
          if (draft.trim() && (await run(() => recordsApi.addNote(record, draft.trim()), "Note added"))) setDraft("");
        }}
      >
        <label htmlFor={`note-${record.type}-${record.id}`} className="sr-only">
          New note
        </label>
        <Textarea
          id={`note-${record.type}-${record.id}`}
          className="min-h-20"
          placeholder="Add a note…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={20000}
        />
        <div>
          <Button type="submit" size="sm" disabled={busy || !draft.trim()}>
            Add note
          </Button>
        </div>
      </form>
      <ul className="divide-y divide-line">
        {notes === null && (
          <li className="px-5 py-4" aria-hidden="true">
            <div className="skeleton h-4 w-2/3" />
          </li>
        )}
        {notes?.length === 0 && <li className="px-5 py-6 text-center text-sm text-muted">No notes yet.</li>}
        {notes?.map((n) => {
          const mine = n.created_by === user?.id || canTidy;
          return (
            <li key={n.id} className="px-5 py-3">
              <div className="mb-1 flex flex-wrap items-center gap-x-2 text-xs text-muted">
                {n.pinned && (
                  <span className="font-medium text-warning">
                    <Icon name="star" className="mr-0.5 inline size-3.5" />
                    Pinned
                  </span>
                )}
                <span>{name(n.created_by)}</span>
                <span aria-hidden="true">·</span>
                <time dateTime={n.created_at}>{formatDateTime(n.created_at)}</time>
                {n.updated_at !== n.created_at && <span>(edited)</span>}
              </div>
              {editing?.id === n.id ? (
                <form
                  className="grid gap-2"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (await run(() => recordsApi.updateNote(n.id, { body: editing.body }), "Note saved")) setEditing(null);
                  }}
                >
                  <label htmlFor={`edit-note-${n.id}`} className="sr-only">
                    Edit note
                  </label>
                  <Textarea id={`edit-note-${n.id}`} value={editing.body} onChange={(e) => setEditing({ id: n.id, body: e.target.value })} autoFocus />
                  <div className="flex gap-2">
                    <Button type="submit" size="sm" disabled={busy || !editing.body.trim()}>
                      Save note
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                      Cancel
                    </Button>
                  </div>
                </form>
              ) : (
                <p className="whitespace-pre-wrap text-sm">{n.body}</p>
              )}
              {mine && editing?.id !== n.id && (
                <div className="mt-1 flex gap-1">
                  <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => void run(() => recordsApi.updateNote(n.id, { pinned: !n.pinned }), n.pinned ? "Unpinned" : "Pinned")}>
                    {n.pinned ? "Unpin" : "Pin"}
                  </Button>
                  <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setEditing({ id: n.id, body: n.body })}>
                    Edit
                  </Button>
                  <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setDeleting(n)}>
                    Delete
                  </Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <ConfirmDialog
        open={!!deleting}
        title="Delete this note?"
        message="It disappears from the record. The audit log keeps a short preview."
        confirmLabel="Delete note"
        busy={busy}
        onConfirm={async () => {
          if (deleting && (await run(() => recordsApi.deleteNote(deleting.id), "Note deleted"))) setDeleting(null);
        }}
        onCancel={() => setDeleting(null)}
      />
    </Panel>
  );
}
