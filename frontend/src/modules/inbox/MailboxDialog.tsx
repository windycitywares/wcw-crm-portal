"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { errorText } from "@/modules/settings/api";
import { inboxApi, PORT_FOR, SECURITY_LABEL, type Mailbox, type MailboxCheck, type MailboxSecurity } from "./api";

const SECURITIES: MailboxSecurity[] = ["ssl", "starttls", "none"];

interface Form {
  address: string;
  display_name: string;
  imap_host: string;
  imap_port: number;
  imap_security: MailboxSecurity;
  imap_user: string;
  imap_password: string;
  folder: string;
  is_active: boolean;
}

const BLANK: Form = { address: "", display_name: "", imap_host: "", imap_port: 993, imap_security: "ssl", imap_user: "", imap_password: "", folder: "INBOX", is_active: true };

function filled(mailbox: Mailbox | null): Form {
  return mailbox
    ? {
        address: mailbox.address,
        display_name: mailbox.display_name ?? "",
        imap_host: mailbox.imap_host,
        imap_port: mailbox.imap_port,
        imap_security: mailbox.imap_security,
        imap_user: mailbox.imap_user ?? "",
        imap_password: "",
        folder: mailbox.folder,
        is_active: mailbox.is_active,
      }
    : BLANK;
}

/**
 * Add or edit a mailbox, and prove the CRM can open it. A new mailbox has to be saved before it can be
 * tested (the test opens the stored one), so the button is only offered once it exists.
 */
export function MailboxDialog({ open, mailbox, onClose, onSaved }: { open: boolean; mailbox: Mailbox | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState<Form>(filled(mailbox));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [check, setCheck] = useState<MailboxCheck | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(filled(mailbox));
    setError(null);
    setCheck(null);
    setDeleting(false);
  }, [open, mailbox]);

  function set(patch: Partial<Form>) {
    setForm((f) => ({ ...f, ...patch }));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!mailbox && !form.imap_password) return setError("The mailbox needs its password.");
    setBusy(true);
    setError(null);
    const data = {
      address: form.address.trim(),
      display_name: form.display_name.trim() || null,
      imap_host: form.imap_host.trim(),
      imap_port: form.imap_port,
      imap_security: form.imap_security,
      imap_user: form.imap_user.trim() || null,
      // Blank on an edit means "keep the one you have" — the API reads an empty string the same way.
      ...(form.imap_password ? { imap_password: form.imap_password } : {}),
      folder: form.folder.trim(),
      is_active: form.is_active,
    };
    try {
      if (mailbox) await inboxApi.update(mailbox.id, data);
      else await inboxApi.create(data);
      toast.push({ title: mailbox ? "Mailbox saved" : "Mailbox added", description: data.address });
      onSaved();
      onClose();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    if (!mailbox) return;
    setChecking(true);
    setCheck(null);
    try {
      setCheck(await inboxApi.test(mailbox.id));
    } catch (err) {
      setCheck({ ok: false, detail: errorText(err), folder: null, messages: null, unseen: null });
    } finally {
      setChecking(false);
    }
  }

  async function remove() {
    if (!mailbox) return;
    setBusy(true);
    try {
      await inboxApi.remove(mailbox.id);
      toast.push({ title: "Mailbox removed", description: mailbox.address });
      setDeleting(false);
      onSaved();
      onClose();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't remove", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={mailbox ? "Edit mailbox" : "Add a mailbox"}
        description="The CRM reads the unread mail in this mailbox and files it under tickets."
        footer={
          <>
            {mailbox && (
              <Button variant="ghost" size="sm" className="mr-auto text-danger" onClick={() => setDeleting(true)}>
                Remove
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" form="mailbox-form" size="sm" disabled={busy}>
              {busy ? "Saving…" : mailbox ? "Save mailbox" : "Add mailbox"}
            </Button>
          </>
        }
      >
        <form id="mailbox-form" onSubmit={save} className="grid gap-4">
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Email address" hint="The address customers write to.">
              {(p) => <Input {...p} type="email" required maxLength={320} autoFocus value={form.address} onChange={(e) => set({ address: e.target.value })} />}
            </Field>
            <Field label="Display name" hint="Optional, for the list.">
              {(p) => <Input {...p} maxLength={160} value={form.display_name} onChange={(e) => set({ display_name: e.target.value })} />}
            </Field>
            <Field label="IMAP server">
              {(p) => <Input {...p} required maxLength={255} placeholder="imap.example.com" value={form.imap_host} onChange={(e) => set({ imap_host: e.target.value })} />}
            </Field>
            <div className="grid grid-cols-[1fr_7rem] gap-3">
              <Field label="Security">
                {(p) => (
                  <Select
                    {...p}
                    value={form.imap_security}
                    onChange={(e) => {
                      const security = e.target.value as MailboxSecurity;
                      // Follow the security with its usual port, unless the port has been set by hand.
                      set({ imap_security: security, imap_port: form.imap_port === PORT_FOR[form.imap_security] ? PORT_FOR[security] : form.imap_port });
                    }}
                  >
                    {SECURITIES.map((s) => (
                      <option key={s} value={s}>
                        {SECURITY_LABEL[s]}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Port">
                {(p) => <Input {...p} type="number" min={1} max={65535} required value={form.imap_port} onChange={(e) => set({ imap_port: Number(e.target.value) })} />}
              </Field>
            </div>
            <Field label="Username" hint="Leave blank to sign in as the address itself.">
              {(p) => <Input {...p} maxLength={320} autoComplete="off" value={form.imap_user} onChange={(e) => set({ imap_user: e.target.value })} />}
            </Field>
            <Field label="Password" hint={mailbox ? "Leave blank to keep the stored one." : "Kept encrypted; the API never returns it."}>
              {(p) => (
                <Input {...p} type="password" maxLength={500} autoComplete="new-password" required={!mailbox} value={form.imap_password} onChange={(e) => set({ imap_password: e.target.value })} />
              )}
            </Field>
            <Field label="Folder" hint="Usually INBOX.">
              {(p) => <Input {...p} required maxLength={120} value={form.folder} onChange={(e) => set({ folder: e.target.value })} />}
            </Field>
            <div className="flex items-end pb-3">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={form.is_active} onChange={(e) => set({ is_active: e.target.checked })} />
                Read this mailbox
              </label>
            </div>
          </div>

          {mailbox && (
            <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
              <Button type="button" variant="secondary" size="sm" disabled={checking} onClick={() => void test()}>
                {checking ? "Opening…" : "Test connection"}
              </Button>
              {check && (
                <span className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
                  <Pill tone={check.ok ? "success" : "danger"}>{check.ok ? "Reachable" : "Not reachable"}</Pill>
                  <span className="min-w-0 break-words text-muted">{check.detail}</span>
                </span>
              )}
            </div>
          )}
        </form>
      </Modal>
      <ConfirmDialog
        open={deleting}
        title="Stop reading this mailbox?"
        message={`${mailbox?.address ?? ""} will be forgotten, password and all. Tickets it has already opened stay.`}
        confirmLabel="Remove mailbox"
        tone="danger"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setDeleting(false)}
      />
    </>
  );
}
