"use client";

import { useEffect, useState } from "react";
import { lookupsApi, type LookupKind, type LookupValue } from "./api";

let cache: Promise<LookupKind[]> | null = null;

/** Type lists (customer types, lead sources …), fetched once per page load. */
export function useLookups() {
  const [kinds, setKinds] = useState<LookupKind[]>([]);
  useEffect(() => {
    cache ??= lookupsApi.kinds().catch(() => {
      cache = null;
      return [];
    });
    let alive = true;
    void cache.then((k) => alive && setKinds(k));
    return () => {
      alive = false;
    };
  }, []);
  const values = (kind: string): LookupValue[] => kinds.find((k) => k.key === kind)?.values ?? [];
  return {
    values,
    /** Active values for pickers, plus `keep` (the record's current value) even if it was deactivated. */
    options: (kind: string, keep?: string | null) => values(kind).filter((v) => v.is_active || v.key === keep),
    find: (kind: string, key: string | null | undefined) => (key ? values(kind).find((v) => v.key === key) : undefined),
  };
}
