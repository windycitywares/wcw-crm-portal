"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, FieldActions, Input } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { urnsApi, type ProductType } from "@/modules/urns/api";
import { SizesPanel, TypePanel } from "@/modules/urns/TypeSetup";

const err = (e: unknown) => (e instanceof Error ? e.message : undefined);

/** Settings → Catalog → Product types & SKUs: pick a type, then its SKU format and its sizes. */
export default function ProductTypesPage() {
  const { can } = useAuth();
  const toast = useToast();
  const canManage = can("channels:manage");
  const [types, setTypes] = useState<ProductType[] | null>(null);
  const [current, setCurrent] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const t = await urnsApi.types();
      setTypes(t);
      const wanted = Number(new URLSearchParams(window.location.search).get("type")); // from Settings → Types
      setCurrent((c) => (c && t.some((x) => x.id === c) ? c : t.some((x) => x.id === wanted) ? wanted : t[0]?.id ?? null));
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't load product types", description: err(e) });
    }
  }, [toast]);
  useEffect(() => { void load(); }, [load]);

  const pick = (id: number) => {
    setCurrent(id);
    window.history.replaceState(null, "", `?type=${id}`);
  };

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const t = await urnsApi.addType({ name: name.trim(), code: code.trim().toUpperCase() || null });
      toast.push({ title: "Product type added", description: `${t.name} starts as one item, one price. Add sizes if it comes in sizes.` });
      setName("");
      setCode("");
      await load();
      pick(t.id);
    } catch (e2) {
      toast.push({ tone: "danger", title: "Couldn't add the product type", description: err(e2) });
    } finally {
      setBusy(false);
    }
  };

  const type = types?.find((t) => t.id === current) ?? null;

  return (
    <div className="space-y-5">
      <PageHeader title="Product types & SKUs"
        description="Each kind of product you sell has its own SKU format and sizes. A type without sizes is sold as one item at one price."
        actions={<ButtonLink href="/settings/extra-costs" size="sm" variant="secondary">Extra costs</ButtonLink>} />

      <Panel>
        <PanelBody className="space-y-4">
          <div role="tablist" aria-label="Product types" className="flex flex-wrap gap-2">
            {types?.map((t) => (
              <button key={t.id} type="button" role="tab" aria-selected={t.id === current} onClick={() => pick(t.id)}
                className={cn("inline-flex h-9 items-center gap-1.5 rounded-[var(--radius-control)] border px-3 text-sm",
                  t.id === current ? "border-accent bg-accent/10 font-semibold text-ink" : "border-line hover:bg-sand", !t.active && "opacity-60")}>
                {t.name}
                {t.code && <span className="rounded bg-sand px-1 font-mono text-[0.6875rem]">{t.code}</span>}
                <span className="text-xs font-normal text-muted">· {t.products}</span>
              </button>
            ))}
            {types === null && <span className="skeleton h-9 w-40" aria-hidden="true" />}
          </div>
          {canManage && (
            <form onSubmit={add} className="grid grid-cols-[minmax(0,1fr)] items-start gap-3 border-t border-line pt-4 sm:grid-cols-[minmax(0,1fr)_9rem_auto]">
              <Field label="New product type">{(p) => <Input {...p} placeholder="Jewelry, Candles…" value={name} required maxLength={60} onChange={(e) => setName(e.target.value)} />}</Field>
              <Field label="Code in the SKU" hint="E.g. J">{(p) => <Input {...p} className="font-mono uppercase" value={code} maxLength={10} pattern="[A-Za-z0-9]+" title="Letters and digits only, e.g. J" onChange={(e) => setCode(e.target.value)} />}</Field>
              <FieldActions><Button type="submit" size="sm" loading={busy}>Add product type</Button></FieldActions>
            </form>
          )}
        </PanelBody>
      </Panel>

      {type && (
        <>
          <TypePanel key={type.id} type={type} canManage={canManage} onChange={() => void load()} />
          <SizesPanel type={type} canManage={canManage} onChange={() => void load()} />
          <p className="text-sm text-muted">
            Extra costs for every {type.name.toLowerCase()} (a box, a velvet bag…) are in{" "}
            <Link href={`/settings/extra-costs#type-${type.id}`} className="font-medium text-accent-strong hover:underline">Extra costs</Link>.
            Names, order and hiding a type are also in <Link href="/settings/types?list=product-types" className="font-medium text-accent-strong hover:underline">Types</Link>.
          </p>
        </>
      )}
    </div>
  );
}
