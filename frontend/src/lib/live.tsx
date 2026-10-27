"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";

/**
 * Live updates (as in the shop admin's LiveProvider): the CRM asks `GET /live/events?after_id=` every 10 seconds while
 * the tab is visible and hands each change to the pages listening for it. A page subscribes with
 * `useLive(["ticket", "contact"], fn)` (record types) and decides what to do — usually show "3 new · Refresh"
 * (LiveUpdatesBar), never reload by itself, so nobody loses their place or a half-typed edit. What you did yourself
 * isn't news to you, so your own changes are left out.
 */

export interface LiveEvent {
  id: number;
  kind: string; // the audit action: ticket.create, contact.update, lead.create …
  entity_type: string;
  ref_id: number | null;
  actor_id: number | null;
  actor_name: string | null;
  at: string;
}

type Listener = { types: string[]; fn: (events: LiveEvent[]) => void };
export type LiveMode = "connecting" | "on" | "off";

const POLL_MS = 10_000;
const Ctx = createContext<{ mode: LiveMode; subscribe: (l: Listener) => () => void } | null>(null);

export function LiveProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const me = user?.id ?? null;
  const meRef = useRef(me);
  meRef.current = me;
  const [mode, setMode] = useState<LiveMode>("connecting");
  const listeners = useRef(new Set<Listener>());

  const subscribe = useCallback((l: Listener) => {
    listeners.current.add(l);
    return () => void listeners.current.delete(l);
  }, []);

  useEffect(() => {
    if (me === null) return;
    let stopped = false;
    let lastId: number | null = null;
    let timer: number | undefined;

    const tick = async () => {
      if (stopped) return;
      if (document.visibilityState === "visible") {
        try {
          const batch = await apiFetch<{ events: LiveEvent[]; last_id: number }>(
            `/live/events${lastId === null ? "" : `?after_id=${lastId}`}`,
          );
          lastId = batch.last_id;
          setMode("on");
          const news = batch.events.filter((e) => e.actor_id === null || e.actor_id !== meRef.current);
          if (news.length) {
            for (const l of listeners.current) {
              const mine = l.types.length ? news.filter((e) => l.types.includes(e.entity_type)) : news;
              if (mine.length) l.fn(mine);
            }
          }
        } catch {
          setMode("off");
        }
      }
      timer = window.setTimeout(() => void tick(), POLL_MS);
    };
    void tick();
    const onShow = () => {
      if (document.visibilityState === "visible") {
        window.clearTimeout(timer);
        void tick();
      }
    };
    document.addEventListener("visibilitychange", onShow);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onShow);
    };
  }, [me]);

  return <Ctx.Provider value={{ mode, subscribe }}>{children}</Ctx.Provider>;
}

/** Call `fn` with the changes to these record types (empty list: everything) made by someone else. */
export function useLive(types: string[], fn: (events: LiveEvent[]) => void) {
  const ctx = useContext(Ctx);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const key = types.join(",");
  useEffect(() => {
    if (!ctx) return;
    return ctx.subscribe({ types: key ? key.split(",") : [], fn: (e) => fnRef.current(e) });
  }, [ctx, key]);
}

export function useLiveMode(): LiveMode {
  return useContext(Ctx)?.mode ?? "off";
}
