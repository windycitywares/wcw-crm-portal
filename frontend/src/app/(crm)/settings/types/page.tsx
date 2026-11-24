"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ColorButton, ColorPicker } from "@/components/ui/ColorPicker";
import { ColorTag } from "@/components/ui/ColorTag";
import { Field, Input, FieldActions } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { ProductTypesPanel } from "@/modules/urns/ProductTypesPanel";
import { urnsApi } from "@/modules/urns/api";
import { errorText, lookupsApi, moved, type LookupKind, type LookupValue } from "@/modules/settings/api";

function ValueRow({
  value,
  index,
  count,
  onSaved,
  onMove,
}: {
  value: LookupValue;
  index: number;
  count: number;
  onSaved: () => void;
  onMove: (delta: -1 | 1) => void;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(value.label);
  const [busy, setBusy] = useState(false);

  async function save(data: Partial<Pick<LookupValue, "label" | "color" | "is_active">>, verb: string) {
    setBusy(true);
    try {
      await lookupsApi.update(value.kind, value.id, data);
      toast.push({ title: verb });
      setEditing(false);
      onSaved();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className={cn("flex flex-wrap items-center gap-3 px-5 py-3", !value.is_active && "opacity-60")}>
      <div className="flex flex-col">
        <button type="button" disabled={index === 0} onClick={() => onMove(-1)} className="grid size-6 place-items-center rounded hover:bg-sand disabled:opacity-30">
          <Icon name="arrowUp" className="size-3.5" />
          <span className="sr-only">Move {value.label} up</span>
        </button>
        <button type="button" disabled={index === count - 1} onClick={() => onMove(1)} className="grid size-6 place-items-center rounded hover:bg-sand disabled:opacity-30">
          <Icon name="arrowDown" className="size-3.5" />
          <span className="sr-only">Move {value.label} down</span>
        </button>
      </div>
      <div className="min-w-0 flex-1">
        {editing ? (
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (label.trim()) void save({ label: label.trim() }, "Renamed");
            }}
          >
            <label className="sr-only" htmlFor={`label-${value.id}`}>
              Name
            </label>
            <Input id={`label-${value.id}`} required value={label} onChange={(e) => setLabel(e.target.value)} className="max-w-xs py-1.5" autoFocus />
            <Button type="submit" size="sm" loading={busy}>
              Save
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setLabel(value.label);
                setEditing(false);
              }}
            >
              Cancel
            </Button>
          </form>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <ColorTag color={value.color}>{value.label}</ColorTag>
            {!value.is_active && <span className="text-xs text-muted">Inactive</span>}
            <span className="font-mono text-xs text-muted">{value.key}</span>
          </div>
        )}
      </div>
      {!editing && (
        <div className="flex items-center gap-2">
          <ColorButton label={`Colour for ${value.label}`} value={value.color} disabled={busy}
            onChange={(c) => void save({ color: c || null }, "Colour changed")} />
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
            <Icon name="edit" className="size-4" />
            Rename
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => void save({ is_active: !value.is_active }, value.is_active ? "Deactivated" : "Activated")}>
            {value.is_active ? "Deactivate" : "Activate"}
          </Button>
        </div>
      )}
    </li>
  );
}

/** Not a lookup list: product types have their own table (SKU code, format, sizes), listed here beside the others. */
const PRODUCT_TYPES = "__product_types";

export default function TypesPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [kinds, setKinds] = useState<LookupKind[] | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [label, setLabel] = useState("");
  const [color, setColor] = useState("");
  const [busy, setBusy] = useState(false);
  const allowed = can("lookups:manage");
  const productTypes = can("channels:manage");
  const [productCount, setProductCount] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await lookupsApi.kinds();
      if (productTypes) void urnsApi.types().then((t) => setProductCount(t.filter((x) => x.active).length)).catch(() => undefined);
      setKinds(data);
      const wanted = new URLSearchParams(window.location.search).get("list");
      setSelected((s) => s || (wanted === "product-types" ? PRODUCT_TYPES : data.find((k) => k.key === wanted)?.key) || data[0]?.key || "");
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't load types", description: errorText(err) });
    }
  }, [toast, productTypes]);

  useEffect(() => {
    if (allowed) void load();
  }, [allowed, load]);

  if (!allowed) return <PageHeader title="Types" description="Only managers and admins can edit type lists." />;

  const kind = kinds?.find((k) => k.key === selected);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!kind || !label.trim()) return;
    setBusy(true);
    try {
      await lookupsApi.create(kind.key, { label: label.trim(), color: color || null });
      toast.push({ title: "Added", description: label.trim() });
      setLabel("");
      setColor("");
      await load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't add", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  async function move(index: number, delta: -1 | 1) {
    if (!kind) return;
    try {
      await lookupsApi.reorder(kind.key, moved(kind.values, index, delta));
      await load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't reorder", description: errorText(err) });
    }
  }

  return (
    <>
      <PageHeader
        title="Types"
        description="The choices people pick from across the CRM. Renaming keeps existing records linked; deactivate a value instead of deleting it."
      />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <nav aria-label="Type lists">
          <ul className="space-y-0.5">
            {(kinds ?? []).map((k) => (
              <li key={k.key}>
                <button
                  type="button"
                  onClick={() => setSelected(k.key)}
                  aria-current={k.key === selected ? "true" : undefined}
                  className={cn(
                    "flex w-full items-center justify-between rounded-[var(--radius-control)] px-3 py-2 text-left text-sm",
                    k.key === selected ? "bg-surface font-medium shadow-[inset_3px_0_0_var(--color-gold)]" : "hover:bg-sand",
                  )}
                >
                  {k.label}
                  <span className="num text-xs text-muted">{k.values.filter((v) => v.is_active).length}</span>
                </button>
              </li>
            ))}
            {productTypes && kinds !== null && (
              <li>
                <button
                  type="button"
                  onClick={() => setSelected(PRODUCT_TYPES)}
                  aria-current={selected === PRODUCT_TYPES ? "true" : undefined}
                  className={cn(
                    "flex w-full items-center justify-between rounded-[var(--radius-control)] px-3 py-2 text-left text-sm",
                    selected === PRODUCT_TYPES ? "bg-surface font-medium shadow-[inset_3px_0_0_var(--color-gold)]" : "hover:bg-sand",
                  )}
                >
                  Product types
                  <span className="num text-xs text-muted">{productCount ?? ""}</span>
                </button>
              </li>
            )}
            {kinds === null && Array.from({ length: 6 }, (_, i) => <li key={i} className="skeleton mx-3 my-2 h-5" aria-hidden="true" />)}
          </ul>
        </nav>
        {selected === PRODUCT_TYPES && productTypes && <ProductTypesPanel onCount={setProductCount} />}
        {kind && (
          <Panel>
            <PanelHeader title={kind.label} description={kind.description} />
            <ul className="divide-y divide-line">
              {kind.values.map((v, i) => (
                <ValueRow key={v.id} value={v} index={i} count={kind.values.length} onSaved={load} onMove={(d) => void move(i, d)} />
              ))}
              {kind.values.length === 0 && <li className="px-5 py-8 text-center text-sm text-muted">No values yet.</li>}
            </ul>
            <form onSubmit={add} className="flex flex-wrap items-start gap-x-3 gap-y-4 border-t border-line px-5 py-4">
              <Field label="New value" className="min-w-0 flex-1 sm:max-w-xs">
                {(p) => <Input {...p} value={label} onChange={(e) => setLabel(e.target.value)} required maxLength={120} />}
              </Field>
              <ColorPicker value={color} onChange={setColor} className="order-last w-full" />
              <FieldActions><Button type="submit" size="sm" loading={busy}>
                <Icon name="plus" className="size-4" />
                Add value
              </Button></FieldActions>
            </form>
          </Panel>
        )}
      </div>
    </>
  );
}
