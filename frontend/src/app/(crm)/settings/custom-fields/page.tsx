"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { customFieldsApi, errorText, moved, type FieldDef, type FieldType } from "@/modules/settings/api";

const CHOICE: FieldType[] = ["select", "multiselect"];

function FieldForm({
  entity,
  field,
  types,
  onClose,
  onSaved,
}: {
  entity: string;
  field: FieldDef | "new";
  types: { key: FieldType; label: string }[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const isNew = field === "new";
  const [label, setLabel] = useState(isNew ? "" : field.label);
  const [type, setType] = useState<FieldType>(isNew ? "text" : field.field_type);
  const [options, setOptions] = useState(isNew ? "" : (field.options ?? []).join("\n"));
  const [required, setRequired] = useState(isNew ? false : field.required);
  const [help, setHelp] = useState(isNew ? "" : (field.help_text ?? ""));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const opts = options
    .split("\n")
    .map((o) => o.trim())
    .filter(Boolean);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const common = { label: label.trim(), required, help_text: help.trim() || null, options: CHOICE.includes(type) ? opts : null };
      if (isNew) await customFieldsApi.create(entity, { ...common, field_type: type });
      else await customFieldsApi.update(entity, field.id, common);
      toast.push({ title: isNew ? "Field added" : "Field saved" });
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
      title={isNew ? "Add a field" : `Edit “${field.label}”`}
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="field-form" size="sm" disabled={busy || !label.trim() || (CHOICE.includes(type) && opts.length === 0)}>
            {busy ? "Saving…" : isNew ? "Add field" : "Save field"}
          </Button>
        </>
      }
    >
      <form id="field-form" onSubmit={save} className="grid gap-4">
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <Field label="Label">{(p) => <Input {...p} required maxLength={120} value={label} onChange={(e) => setLabel(e.target.value)} />}</Field>
        <Field label="Type" hint={isNew ? "Can't be changed later — stored values must stay valid." : "The type is fixed once a field exists."}>
          {(p) => (
            <Select {...p} value={type} disabled={!isNew} onChange={(e) => setType(e.target.value as FieldType)}>
              {types.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {CHOICE.includes(type) && (
          <Field label="Options" hint="One per line.">
            {(p) => <Textarea {...p} value={options} onChange={(e) => setOptions(e.target.value)} />}
          </Field>
        )}
        <Field label="Help text" hint="Optional. Shown under the field.">
          {(p) => <Input {...p} maxLength={255} value={help} onChange={(e) => setHelp(e.target.value)} />}
        </Field>
        <label className="flex items-center gap-3 text-sm">
          <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={required} onChange={(e) => setRequired(e.target.checked)} />
          Required
        </label>
      </form>
    </Modal>
  );
}

export default function CustomFieldsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [recordTypes, setRecordTypes] = useState<{ key: string; label: string }[] | null>(null);
  const [types, setTypes] = useState<{ key: FieldType; label: string }[]>([]);
  const [entity, setEntity] = useState("");
  const [fields, setFields] = useState<FieldDef[] | null>(null);
  const [editing, setEditing] = useState<FieldDef | "new" | null>(null);
  const allowed = can("lookups:manage");

  useEffect(() => {
    if (!allowed) return;
    Promise.all([customFieldsApi.recordTypes(), customFieldsApi.types()])
      .then(([rt, ft]) => {
        setRecordTypes(rt);
        setTypes(ft);
        setEntity((e) => e || rt[0]?.key || "");
      })
      .catch((err) => toast.push({ tone: "danger", title: "Couldn't load", description: errorText(err) }));
  }, [allowed, toast]);

  const load = useCallback(async () => {
    if (!entity) return;
    try {
      setFields(await customFieldsApi.list(entity));
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't load fields", description: errorText(err) });
    }
  }, [entity, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!allowed) return <PageHeader title="Custom fields" description="Only managers and admins can manage custom fields." />;

  async function toggle(f: FieldDef) {
    try {
      await customFieldsApi.update(entity, f.id, { is_active: !f.is_active });
      toast.push({ title: f.is_active ? "Field hidden" : "Field shown" });
      await load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save", description: errorText(err) });
    }
  }

  async function move(index: number, delta: -1 | 1) {
    if (!fields) return;
    try {
      setFields(await customFieldsApi.reorder(entity, moved(fields, index, delta)));
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't reorder", description: errorText(err) });
    }
  }

  const typeLabel = (t: FieldType) => types.find((x) => x.key === t)?.label ?? t;

  return (
    <>
      <PageHeader
        title="Custom fields"
        description="Extra fields for your records — shown on their forms and saved with them."
        actions={
          entity ? (
            <Button size="sm" onClick={() => setEditing("new")}>
              <Icon name="plus" className="size-4" />
              Add field
            </Button>
          ) : undefined
        }
      />
      {recordTypes && recordTypes.length === 0 ? (
        <Panel className="px-5 py-10 text-center text-sm text-muted">
          No record types yet. Custom fields become available here as modules like Customers arrive.
        </Panel>
      ) : (
        <Panel>
          <PanelHeader
            title="Fields"
            actions={
              <Field label="Record type" className="w-48">
                {(p) => (
                  <Select {...p} value={entity} onChange={(e) => setEntity(e.target.value)}>
                    {(recordTypes ?? []).map((r) => (
                      <option key={r.key} value={r.key}>
                        {r.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            }
          />
          <ul className="divide-y divide-line">
            {(fields ?? []).map((f, i) => (
              <li key={f.id} className={cn("flex flex-wrap items-center gap-3 px-5 py-3", !f.is_active && "opacity-60")}>
                <div className="flex flex-col">
                  <button type="button" disabled={i === 0} onClick={() => void move(i, -1)} className="grid size-6 place-items-center rounded hover:bg-sand disabled:opacity-30">
                    <Icon name="arrowUp" className="size-3.5" />
                    <span className="sr-only">Move {f.label} up</span>
                  </button>
                  <button
                    type="button"
                    disabled={i === (fields?.length ?? 0) - 1}
                    onClick={() => void move(i, 1)}
                    className="grid size-6 place-items-center rounded hover:bg-sand disabled:opacity-30"
                  >
                    <Icon name="arrowDown" className="size-3.5" />
                    <span className="sr-only">Move {f.label} down</span>
                  </button>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {f.label}
                    <Pill dot={false}>{typeLabel(f.field_type)}</Pill>
                    {f.required && <Pill tone="warning">Required</Pill>}
                    {!f.is_active && <Pill>Hidden</Pill>}
                  </p>
                  <p className="text-xs text-muted">
                    <span className="font-mono">{f.key}</span>
                    {f.options?.length ? ` · ${f.options.join(", ")}` : ""}
                  </p>
                </div>
                <Button size="sm" variant="ghost" onClick={() => setEditing(f)}>
                  <Icon name="edit" className="size-4" />
                  Edit<span className="sr-only"> {f.label}</span>
                </Button>
                <Button size="sm" variant="secondary" onClick={() => void toggle(f)}>
                  {f.is_active ? "Hide" : "Show"}
                  <span className="sr-only"> {f.label}</span>
                </Button>
              </li>
            ))}
            {fields && fields.length === 0 && <li className="px-5 py-10 text-center text-sm text-muted">No custom fields yet.</li>}
          </ul>
        </Panel>
      )}
      {editing && entity && <FieldForm entity={entity} field={editing} types={types} onClose={() => setEditing(null)} onSaved={load} />}
    </>
  );
}
