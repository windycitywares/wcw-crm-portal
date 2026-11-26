"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Input, FieldActions } from "@/components/ui/Field";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { urnsApi, type ProductType, type UrnSize } from "@/modules/urns/api";
import { TIPS } from "@/modules/help/tips";

const err = (e: unknown) => (e instanceof Error ? e.message : undefined);

/** A product type's SKU format and its sizes (Settings → Product types & SKUs). */
export function TypePanel({ type, canManage, onChange }: { type: ProductType; canManage: boolean; onChange: () => void }) {
  const toast = useToast();
  const [draft, setDraft] = useState({ name: type.name, code: type.code ?? "", template: type.template, size_format: type.size_format, separator: type.separator });
  const [check, setCheck] = useState<{ problems: string[]; examples: string[] }>({ problems: type.problems, examples: type.examples });
  const [busy, setBusy] = useState(false);
  const hasSizes = type.sizes.some((s) => s.active);
  const changed = draft.name !== type.name || draft.code !== (type.code ?? "") || draft.template !== type.template
    || draft.size_format !== type.size_format || draft.separator !== type.separator;

  useEffect(() => {
    const t = setTimeout(() => {
      urnsApi.checkType(type.id, { template: draft.template, size_format: draft.size_format, separator: draft.separator, code: draft.code })
        .then(setCheck).catch(() => undefined);
    }, 300);
    return () => clearTimeout(t);
  }, [draft.template, draft.size_format, draft.separator, draft.code, type.id]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await urnsApi.editType(type.id, { ...draft, code: draft.code.trim() || null });
      toast.push({ title: "Product type saved", description: `${draft.name}: its products' SKUs follow the new format in the CRM. Nothing was sent to Etsy.` });
      onChange();
    } catch (e2) {
      toast.push({ tone: "danger", title: "Couldn't save the type", description: err(e2) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title={`${type.name}: SKU format`}
        description={`${type.products} product${type.products === 1 ? "" : "s"} · ${hasSizes ? "comes in sizes" : "sold as one item, one price"}`}
        actions={canManage ? <Button size="sm" variant="ghost" disabled={busy}
          onClick={() => void urnsApi.editType(type.id, { active: !type.active }).then(onChange)}>{type.active ? "Turn off" : "Turn on"}</Button> : undefined} />
      <PanelBody>
        <form onSubmit={save} className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-6">
          <Field label="Name" className="sm:col-span-2">{(p) => <Input {...p} required value={draft.name} maxLength={60} disabled={!canManage} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />}</Field>
          <Field label="Short code" tip={TIPS.typeCode} hint="What {type} writes, e.g. U">{(p) => <Input {...p} className="font-mono" value={draft.code} maxLength={10} disabled={!canManage} onChange={(e) => setDraft({ ...draft, code: e.target.value.toUpperCase() })} />}</Field>
          <Field label="Template" className="sm:col-span-3" tip={TIPS.skuTemplate}
            hint={`{supplier:3} supplier number · {product:4} product number${hasSizes ? " · {sizes} the pieces" : ""} · {type} the short code · {-option} reserved`}>
            {(p) => <Input {...p} className="font-mono" value={draft.template} maxLength={80} disabled={!canManage} onChange={(e) => setDraft({ ...draft, template: e.target.value })} />}
          </Field>
          {hasSizes && (
            <>
              <Field label="One size" tip={TIPS.sizeFormat} hint="{code} and {qty}">{(p) => <Input {...p} className="font-mono" value={draft.size_format} maxLength={20} disabled={!canManage} onChange={(e) => setDraft({ ...draft, size_format: e.target.value })} />}</Field>
              <Field label="Between sizes" tip={TIPS.sizeSeparator}>{(p) => <Input {...p} className="font-mono" value={draft.separator} maxLength={3} disabled={!canManage} onChange={(e) => setDraft({ ...draft, separator: e.target.value })} />}</Field>
            </>
          )}
          <div className="sm:col-span-6">
            {check.problems.length > 0 ? (
              <ul role="alert" className="space-y-1 text-sm text-danger">{check.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            ) : (
              <p className="text-sm text-muted">Examples: {check.examples.map((x) => <code key={x} className="mr-2 rounded bg-sand px-1.5 py-0.5 text-ink">{x}</code>)}</p>
            )}
          </div>
          {canManage && (
            <div className="flex gap-2 sm:col-span-6">
              <Button type="submit" size="sm" loading={busy} disabled={!changed || check.problems.length > 0}>Save type</Button>
              {changed && <Button type="button" size="sm" variant="ghost"
                onClick={() => setDraft({ name: type.name, code: type.code ?? "", template: type.template, size_format: type.size_format, separator: type.separator })}>Undo changes</Button>}
            </div>
          )}
        </form>
      </PanelBody>
    </Panel>
  );
}

export function SizesPanel({ type, canManage, onChange }: { type: ProductType; canManage: boolean; onChange: () => void }) {
  const sizes: UrnSize[] = type.sizes;
  const toast = useToast();
  const [editing, setEditing] = useState<number | null>(null);
  const [label, setLabel] = useState("");
  const [aliases, setAliases] = useState("");
  const [code, setCode] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [busy, setBusy] = useState(false);

  const act = async (fn: () => Promise<unknown>, title: string, description?: string) => {
    setBusy(true);
    try {
      await fn();
      toast.push({ title, description });
      setEditing(null);
      onChange();
    } catch (e) {
      toast.push({ tone: "danger", title: "That didn't work", description: err(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title={`${type.name}: sizes`} description={sizes.length ? "In the order they appear in a SKU. Words that mean a size in Etsy variation names help the CRM read them." : "None: each product of this type is one item at one price. Add a size if it comes in sizes."} />
      <PanelBody className="space-y-4">
        <ul className="divide-y divide-line">
          {sizes.map((s) => (
            <li key={s.id} className="py-3">
              {editing === s.id ? (
                <form className="grid grid-cols-[minmax(0,1fr)] gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]"
                  onSubmit={(e) => { e.preventDefault(); void act(() => urnsApi.editSize(s.id, { label, aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean) }), "Size saved", label); }}>
                  <Field label="Name">{(p) => <Input {...p} required value={label} maxLength={40} onChange={(e) => setLabel(e.target.value)} />}</Field>
                  <Field label="Words that mean this size" tip={TIPS.sizeWords} hint="Separated by commas, e.g. large, adult">{(p) => <Input {...p} maxLength={200} value={aliases} onChange={(e) => setAliases(e.target.value)} />}</Field>
                  <div className="flex items-end gap-1">
                    <Button type="submit" size="sm" loading={busy}>Save size</Button>
                    <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                  </div>
                </form>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 font-medium">{s.label} <code className="rounded bg-sand px-1.5 text-xs">{s.code}</code>{!s.active && <Badge>Off</Badge>}</div>
                    <div className="text-xs text-muted">{s.aliases.length ? `Also read from: ${s.aliases.join(", ")}` : "No extra words"}</div>
                  </div>
                  {canManage && (
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => { setEditing(s.id); setLabel(s.label); setAliases(s.aliases.join(", ")); }}>Edit</Button>
                      <Button size="sm" variant="ghost" disabled={busy}
                        onClick={() => void act(() => urnsApi.editSize(s.id, { active: !s.active }), s.active ? "Size turned off" : "Size turned on", s.label)}>
                        {s.active ? "Turn off" : "Turn on"}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
        {canManage && (
          <form className="grid grid-cols-[minmax(0,1fr)] items-start gap-2 border-t border-line pt-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]"
            onSubmit={(e) => { e.preventDefault(); void act(() => urnsApi.addSize({ type_id: type.id, code: code.trim(), label: newLabel.trim() || `${code.trim()} inch` }), "Size added", code)
              .then(() => { setCode(""); setNewLabel(""); }); }}>
            <Field label="Code in the SKU" hint="E.g. 7">{(p) => <Input {...p} value={code} required maxLength={10} pattern="[A-Za-z0-9]+" title="Letters and numbers only, no spaces." onChange={(e) => setCode(e.target.value)} />}</Field>
            <Field label="Name">{(p) => <Input {...p} placeholder="7 inch" value={newLabel} maxLength={40} onChange={(e) => setNewLabel(e.target.value)} />}</Field>
            <FieldActions><Button type="submit" size="sm" loading={busy}>Add size</Button></FieldActions>
          </form>
        )}
      </PanelBody>
    </Panel>
  );
}
