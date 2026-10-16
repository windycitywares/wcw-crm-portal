"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { COLOR_OPTIONS, ColorTag } from "@/components/ui/ColorTag";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { errorText, tagsApi, type Tag } from "@/modules/settings/api";

function TagForm({ tag, onClose, onSaved }: { tag: Tag | "new"; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const isNew = tag === "new";
  const [name, setName] = useState(isNew ? "" : tag.name);
  const [color, setColor] = useState(isNew ? "" : (tag.color ?? ""));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isNew) await tagsApi.create({ name: name.trim(), color: color || null });
      else await tagsApi.update(tag.id, { name: name.trim(), color: color || null });
      toast.push({ title: isNew ? "Tag added" : "Tag saved" });
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
      title={isNew ? "Add a tag" : `Edit “${tag.name}”`}
      size="sm"
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="tag-form" size="sm" disabled={busy || !name.trim()}>
            {busy ? "Saving…" : isNew ? "Add tag" : "Save tag"}
          </Button>
        </>
      }
    >
      <form id="tag-form" onSubmit={save} className="grid gap-4">
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <Field label="Name">{(p) => <Input {...p} required maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
        <Field label="Colour">
          {(p) => (
            <Select {...p} value={color} onChange={(e) => setColor(e.target.value)}>
              {COLOR_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </form>
    </Modal>
  );
}

export default function TagsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [tags, setTags] = useState<Tag[] | null>(null);
  const [editing, setEditing] = useState<Tag | "new" | null>(null);
  const [deleting, setDeleting] = useState<Tag | null>(null);
  const [busy, setBusy] = useState(false);
  const allowed = can("lookups:manage");

  const load = useCallback(async () => {
    try {
      setTags(await tagsApi.search(q));
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't load tags", description: errorText(err) });
    }
  }, [q, toast]);

  useEffect(() => {
    if (!allowed) return;
    const t = window.setTimeout(load, q ? 250 : 0);
    return () => window.clearTimeout(t);
  }, [allowed, load, q]);

  if (!allowed) return <PageHeader title="Tags" description="Only managers and admins can manage tags." />;

  async function remove() {
    if (!deleting) return;
    setBusy(true);
    try {
      await tagsApi.remove(deleting.id);
      toast.push({ title: "Tag deleted", description: deleting.name });
      setDeleting(null);
      await load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't delete", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<Tag>[] = [
    { key: "name", header: "Tag", cell: (t) => <ColorTag color={t.color}>{t.name}</ColorTag> },
    { key: "uses", header: "Used on", align: "right", cell: (t) => <span className="num">{t.uses ?? 0}</span> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (t) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" onClick={() => setEditing(t)}>
            <Icon name="edit" className="size-4" />
            Edit<span className="sr-only"> {t.name}</span>
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setDeleting(t)}>
            <Icon name="trash" className="size-4" />
            Delete<span className="sr-only"> {t.name}</span>
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Tags"
        description="Free labels anyone can add to customers, tickets and deals. Tidy them up here."
        actions={
          <Button size="sm" onClick={() => setEditing("new")}>
            <Icon name="plus" className="size-4" />
            Add tag
          </Button>
        }
      />
      <Panel>
        <div className="border-b border-line px-4 py-3">
          <Field label="Search" className="max-w-xs">
            {(p) => <Input {...p} type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tag name" />}
          </Field>
        </div>
        <DataTable caption="Tags" columns={columns} rows={tags} rowKey={(t) => t.id} empty="No tags yet — they appear here as people add them to records." />
      </Panel>
      {editing && <TagForm tag={editing} onClose={() => setEditing(null)} onSaved={load} />}
      <ConfirmDialog
        open={!!deleting}
        title="Delete this tag?"
        message={
          <>
            “{deleting?.name}” will be removed from {deleting?.uses ?? 0} record(s). This can&apos;t be undone.
          </>
        }
        confirmLabel="Delete tag"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setDeleting(null)}
      />
    </>
  );
}
