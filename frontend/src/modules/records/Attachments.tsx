"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { ConfirmDialog } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { apiDownload } from "@/lib/client-api";
import { formatDateTime } from "@/lib/utils";
import { recordsApi, type Attachment, type RecordRef } from "./api";

/** "820 KB" — enough to judge whether to fetch a file on a phone. */
function fileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb < 10 ? kb.toFixed(1) : Math.round(kb)} KB`;
  const mb = kb / 1024;
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`;
}

/**
 * The files kept against a record — what a customer sent with their message, today. Anyone who can see
 * the record can fetch one; removing one changes the record, so the button takes the right to change it.
 * Renders nothing at all when there are no files: a conversation with no attachments has nothing to say.
 */
export function Attachments({
  record,
  canEdit,
  refreshKey,
}: {
  record: RecordRef;
  canEdit: boolean;
  refreshKey?: string;
}) {
  const toast = useToast();
  const [files, setFiles] = useState<Attachment[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState<Attachment | null>(null);

  const load = useCallback(() => {
    recordsApi
      .attachments(record)
      .then(setFiles)
      .catch(() => setFiles([]));
  }, [record.type, record.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  async function download(file: Attachment) {
    try {
      await apiDownload(recordsApi.attachmentUrl(file.id), file.filename);
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't download", description: err instanceof Error ? err.message : undefined });
    }
  }

  async function remove(file: Attachment) {
    setBusy(true);
    try {
      await recordsApi.deleteAttachment(file.id);
      toast.push({ title: "File removed", description: file.filename });
      setRemoving(null);
      load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't remove the file", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  if (!files?.length) return null;

  return (
    <section className="grid gap-2 border-t border-line pt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
        {files.length === 1 ? "1 file" : `${files.length} files`}
      </h3>
      <ul className="grid gap-1.5">
        {files.map((f) => (
          <li
            key={f.id}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[var(--radius-control)] border border-line bg-sand px-3 py-2"
          >
            <Button size="sm" variant="ghost" className="h-7 gap-1.5 px-2 text-xs" onClick={() => void download(f)}>
              <Icon name="download" className="size-3.5" />
              <span className="max-w-[16rem] truncate">{f.filename}</span>
            </Button>
            <span className="text-xs text-muted">
              {fileSize(f.size)} · {formatDateTime(f.created_at)}
            </span>
            {canEdit && (
              <Button
                size="sm"
                variant="ghost"
                className="ml-auto h-7 px-2 text-xs"
                onClick={() => setRemoving(f)}
                aria-label={`Remove ${f.filename}`}
              >
                <Icon name="trash" className="size-3.5" />
              </Button>
            )}
          </li>
        ))}
      </ul>
      <ConfirmDialog
        open={!!removing}
        title="Remove this file?"
        message={
          removing
            ? `“${removing.filename}” disappears from the record. The audit log keeps the name and size.`
            : ""
        }
        confirmLabel="Remove file"
        busy={busy}
        onConfirm={() => {
          if (removing) void remove(removing);
        }}
        onCancel={() => setRemoving(null)}
      />
    </section>
  );
}
