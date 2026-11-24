"use client";

import { useEffect, useState } from "react";
import { suppliersApi, type Supplier } from "@/modules/suppliers/api";

let cache: Promise<Supplier[]> | null = null;

/** Supplier records (their CRM id is the number in the SKU), active ones, by name. Loaded once per page view. */
export function useSupplierRecords() {
  const [rows, setRows] = useState<Supplier[]>([]);
  useEffect(() => {
    let alive = true;
    cache ??= suppliersApi.list(1, 200, undefined, undefined, "active").then((p) => p.items).catch(() => { cache = null; return []; });
    void cache.then((r) => alive && setRows(r));
    return () => { alive = false; };
  }, []);
  return rows;
}

/** Every size of every product type (filter by `type_id`). */
export function useSizes() {
  const [sizes, setSizes] = useState<import("./api").UrnSize[]>([]);
  useEffect(() => {
    let alive = true;
    void import("./api").then(({ urnsApi }) => urnsApi.sizes()).then((s) => alive && setSizes(s)).catch(() => undefined);
    return () => { alive = false; };
  }, []);
  return sizes;
}

/** The product types, loaded once per page. */
export function useTypes() {
  const [types, setTypes] = useState<import("./api").ProductType[]>([]);
  useEffect(() => {
    let alive = true;
    void import("./api").then(({ urnsApi }) => urnsApi.types()).then((t) => alive && setTypes(t)).catch(() => undefined);
    return () => { alive = false; };
  }, []);
  return types;
}
