"use client";

import { useEffect, useState } from "react";
import { recordsApi, type Colleague } from "./api";

let cache: Promise<Colleague[]> | null = null;

/** Colleagues by id (fetched once per page load) — for "added by …" lines and assignee pickers. */
export function useDirectory() {
  const [people, setPeople] = useState<Map<number, Colleague>>(new Map());
  useEffect(() => {
    cache ??= recordsApi.directory().catch(() => {
      cache = null;
      return [];
    });
    let alive = true;
    void cache.then((list) => alive && setPeople(new Map(list.map((c) => [c.id, c]))));
    return () => {
      alive = false;
    };
  }, []);
  return {
    people,
    name: (id: number | null | undefined) => (id == null ? "System" : (people.get(id)?.full_name ?? "Former user")),
  };
}
