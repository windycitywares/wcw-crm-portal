"use client";

import { useCallback, useEffect, useState } from "react";
import { ButtonLink } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { urnsApi, type CostExtra, type ProductType } from "@/modules/urns/api";
import { ExtrasPanel } from "@/modules/urns/ExtrasPanel";

const err = (e: unknown) => (e instanceof Error ? e.message : undefined);

/** Settings → Catalog → Extra costs: what's added to (or taken off) the supplier price for every product, then for
 *  every product of each type. A single product's own extras stay on that product's page. */
export default function ExtraCostsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const canManage = can("channels:manage");
  const [types, setTypes] = useState<ProductType[]>([]);
  const [shared, setShared] = useState<CostExtra[] | null>(null);
  const [byType, setByType] = useState<Record<number, CostExtra[]>>({});

  const load = useCallback(async () => {
    try {
      const [t, e] = await Promise.all([urnsApi.types(), urnsApi.sharedExtras()]);
      setTypes(t);
      setShared(e);
      const lists = await Promise.all(t.map((x) => urnsApi.sharedExtras(x.id).then((l) => [x.id, l] as const)));
      setByType(Object.fromEntries(lists));
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't load extra costs", description: err(e) });
    }
  }, [toast]);
  useEffect(() => { void load(); }, [load]);

  // Arriving from a type's page (#type-<id>) scrolls to that type once its panel exists.
  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (id && types.length) document.getElementById(id)?.scrollIntoView({ block: "start" });
  }, [types]);

  return (
    <div className="space-y-5">
      <PageHeader title="Extra costs"
        description="Added to or taken off the supplier price — per piece or per order, as an amount or a percentage. Minus amounts subtract. A single product's own extras are on its page."
        actions={<ButtonLink href="/settings/product-types" size="sm" variant="secondary">Product types &amp; SKUs</ButtonLink>} />
      {shared && (
        <ExtrasPanel urnId={null} extras={shared} sizes={types.flatMap((t) => t.sizes)} canManage={canManage} onChange={() => void load()}
          title="For every product" description="Whatever the type, e.g. a shipping box per order." />
      )}
      {types.filter((t) => t.active || (byType[t.id]?.length ?? 0) > 0).map((t) => (
        <section key={t.id} id={`type-${t.id}`} className="scroll-mt-20">
          <ExtrasPanel urnId={null} typeId={t.id} extras={byType[t.id] ?? []} sizes={t.sizes} canManage={canManage} onChange={() => void load()}
            title={`For every ${t.name.toLowerCase()}`} description={`Only products of type ${t.name}.`} />
        </section>
      ))}
    </div>
  );
}
