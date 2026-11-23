"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { urnsApi, type UrnSummary } from "./api";

/** On the Etsy dashboard: new listings without a urn, and urn setup still to do, so costs come from SKUs. */
export function UrnSetupNotice() {
  const [s, setS] = useState<UrnSummary | null>(null);
  useEffect(() => { urnsApi.summary().then(setS).catch(() => setS(null)); }, []);
  if (!s) return null;
  const todo = [
    s.listings_without_urn && `${s.listings_without_urn} listing${s.listings_without_urn === 1 ? "" : "s"} without a product`,
    s.no_supplier && `${s.no_supplier} product${s.no_supplier === 1 ? "" : "s"} without a supplier`,
    s.to_review && `${s.to_review} variation${s.to_review === 1 ? "" : "s"} to check`,
    s.no_prices && `${s.no_prices} product${s.no_prices === 1 ? "" : "s"} without prices`,
  ].filter(Boolean) as string[];
  if (!todo.length) return null;
  return (
    <div role="status" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-card)] bg-warning/10 px-4 py-3 text-sm ring-1 ring-warning/30">
      <span><strong>Needs a product setup:</strong> {todo.join(" · ")}. Until then those orders' costs aren't worked out from SKUs.</span>
      <Link href="/channels/etsy/products" className="font-medium text-accent-strong hover:underline">Open Products</Link>
    </div>
  );
}
