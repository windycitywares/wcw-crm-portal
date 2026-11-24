"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, FieldActions, Input } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import { urnsApi, type ProductType } from "@/modules/urns/api";

const err = (e: unknown) => (e instanceof Error ? e.message : undefined);
const CODE = { pattern: "[A-Za-z0-9]+", title: "Letters and digits only, e.g. J" };

/** What the Etsy products are (Urn, Jewelry, Candles…) as one of the type lists in Settings → Types. Names, codes,
 *  order and on/off live here; each type's SKU format, sizes and extra costs are in Settings → Catalog, one link away. */
export function ProductTypesPanel({ onCount }: { onCount?: (n: number) => void }) {
  const toast = useToast();
  const [types, setTypes] = useState<ProductType[] | null>(null);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const t = await urnsApi.types();
      setTypes(t);
      onCount?.(t.filter((x) => x.active).length);
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't load product types", description: err(e) });
    }
  }, [toast, onCount]);
  useEffect(() => { void load(); }, [load]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const t = await urnsApi.addType({ name: name.trim(), code: code.trim().toUpperCase() || null });
      toast.push({ title: "Product type added", description: `${t.name}. Set its SKU format and sizes next.` });
      setName("");
      setCode("");
      await load();
    } catch (e2) {
      toast.push({ tone: "danger", title: "Couldn't add the product type", description: err(e2) });
    } finally {
      setBusy(false);
    }
  }

  async function move(index: number, delta: -1 | 1) {
    if (!types) return;
    const a = types[index], b = types[index + delta];
    if (!b) return;
    try {
      // Positions may tie (older rows); spread them out so the swap always sticks.
      await Promise.all([urnsApi.editType(a.id, { position: (index + delta) * 10 + 10 }), urnsApi.editType(b.id, { position: index * 10 + 10 })]);
      await load();
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't reorder", description: err(e) });
    }
  }

  return (
    <Panel>
      <PanelHeader title="Product types"
        description="What your Etsy products are — Urn, Jewelry, Candles… Each type has its own code in the SKU, its own sizes and its own SKU format." />
      <ul className="divide-y divide-line">
        {types?.map((t, i) => (
          <TypeRow key={t.id} type={t} index={i} count={types.length} onSaved={load} onMove={(d) => void move(i, d)} />
        ))}
        {types === null && Array.from({ length: 2 }, (_, i) => <li key={i} className="skeleton mx-5 my-4 h-6" aria-hidden="true" />)}
        {types?.length === 0 && <li className="px-5 py-8 text-center text-sm text-muted">No product types yet.</li>}
      </ul>
      <form onSubmit={add} className="grid grid-cols-[minmax(0,1fr)] items-start gap-3 border-t border-line px-5 py-4 sm:grid-cols-[minmax(0,1fr)_9rem_auto]">
        <Field label="New product type">
          {(p) => <Input {...p} required maxLength={60} placeholder="Jewelry, Candles…" value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label="Code in the SKU" hint="E.g. J">
          {(p) => <Input {...p} maxLength={10} {...CODE} className="font-mono uppercase" value={code} onChange={(e) => setCode(e.target.value)} />}
        </Field>
        <FieldActions>
          <Button type="submit" size="sm" loading={busy}>
            <Icon name="plus" className="size-4" />
            Add product type
          </Button>
        </FieldActions>
      </form>
    </Panel>
  );
}

function TypeRow({ type: t, index, count, onSaved, onMove }: {
  type: ProductType; index: number; count: number; onSaved: () => void; onMove: (d: -1 | 1) => void;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(t.name);
  const [code, setCode] = useState(t.code ?? "");
  const [busy, setBusy] = useState(false);

  async function save(data: Parameters<typeof urnsApi.editType>[1], verb: string) {
    setBusy(true);
    try {
      await urnsApi.editType(t.id, data);
      toast.push({ title: verb, description: t.name });
      setEditing(false);
      onSaved();
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't save the product type", description: err(e) });
    } finally {
      setBusy(false);
    }
  }

  const codeChanged = (code.trim().toUpperCase() || null) !== (t.code ?? null);

  return (
    <li className={cn("flex flex-wrap items-center gap-3 px-5 py-3", !t.active && "opacity-60")}>
      <div className="flex flex-col">
        <button type="button" disabled={index === 0} onClick={() => onMove(-1)} className="grid size-6 place-items-center rounded hover:bg-sand disabled:opacity-30">
          <Icon name="arrowUp" className="size-3.5" />
          <span className="sr-only">Move {t.name} up</span>
        </button>
        <button type="button" disabled={index === count - 1} onClick={() => onMove(1)} className="grid size-6 place-items-center rounded hover:bg-sand disabled:opacity-30">
          <Icon name="arrowDown" className="size-3.5" />
          <span className="sr-only">Move {t.name} down</span>
        </button>
      </div>
      <div className="min-w-0 flex-1">
        {editing ? (
          <form className="grid grid-cols-[minmax(0,1fr)] items-start gap-2 sm:grid-cols-[minmax(0,1fr)_8rem_auto]"
            onSubmit={(e) => { e.preventDefault(); void save({ name: name.trim(), code: code.trim().toUpperCase() || null }, "Product type saved"); }}>
            <Field label="Name">{(p) => <Input {...p} required maxLength={60} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}</Field>
            <Field label="Code" hint={codeChanged && t.products ? `Changes the SKUs of ${t.products} products` : undefined}>
              {(p) => <Input {...p} maxLength={10} {...CODE} className="font-mono uppercase" value={code} onChange={(e) => setCode(e.target.value)} />}
            </Field>
            <FieldActions>
              <Button type="submit" size="sm" loading={busy}>Save</Button>
              <Button size="sm" variant="ghost" onClick={() => { setName(t.name); setCode(t.code ?? ""); setEditing(false); }}>Cancel</Button>
            </FieldActions>
          </form>
        ) : (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-medium">{t.name}</span>
            {t.code ? <span className="rounded bg-sand px-1.5 py-0.5 font-mono text-xs">{t.code}</span> : <span className="text-xs text-muted">No code</span>}
            {!t.active && <Badge variant="neutral">Hidden</Badge>}
            {t.problems.length > 0 && <Badge variant="warning">SKU format needs a look</Badge>}
            <span className="w-full text-xs text-muted">
              <Link href={`/channels/etsy/products?type=${t.id}`} className="hover:text-ink hover:underline">{t.products} {t.products === 1 ? "product" : "products"}</Link>
              {" · "}{t.sizes.filter((s) => s.active).length} sizes
              {t.examples[0] && <> · e.g. <span className="font-mono">{t.examples[0]}</span></>}
            </span>
          </div>
        )}
      </div>
      {!editing && (
        <div className="flex flex-wrap items-center gap-2">
          <ButtonLink href={`/settings/product-types?type=${t.id}`} size="sm" variant="ghost">SKU format &amp; sizes</ButtonLink>
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
            <Icon name="edit" className="size-4" />
            Edit
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => void save({ active: !t.active }, t.active ? "Product type hidden" : "Product type shown")}>
            {t.active ? "Hide" : "Show"}
          </Button>
        </div>
      )}
    </li>
  );
}
