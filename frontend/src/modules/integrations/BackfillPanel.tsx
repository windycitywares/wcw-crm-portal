"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Modal";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { formatDateTime } from "@/lib/utils";
import { errorText } from "@/modules/settings/api";
import { shopApi, type Backfill } from "./api";

const PHASE: Record<Backfill["phase"], string> = { customers: "customer accounts", orders: "orders", newsletter: "newsletter consent" };

/** Test the shop API and run the one-off import of existing customers, orders and consent. */
export function BackfillPanel({ tokenSet }: { tokenSet: boolean }) {
  const toast = useToast();
  const [state, setState] = useState<Backfill | null>(null);
  const [test, setTest] = useState<{ ok: boolean; detail: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => shopApi.backfill().then(setState).catch(() => setState(null)), []);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (state?.status !== "running") return;
    const t = setInterval(() => void load(), 10_000);
    return () => clearInterval(t);
  }, [state?.status, load]);

  async function runTest() {
    setTesting(true);
    setTest(null);
    try {
      setTest(await shopApi.test());
    } catch (err) {
      setTest({ ok: false, detail: errorText(err) });
    } finally {
      setTesting(false);
    }
  }

  async function start() {
    setBusy(true);
    try {
      setState(await shopApi.startBackfill());
      toast.push({ title: "Import started", description: "It runs in the background, a few hundred records a minute." });
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't start the import", description: errorText(err) });
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  async function cancel() {
    setBusy(true);
    try {
      setState(await shopApi.cancelBackfill());
      toast.push({ title: "Import stopped" });
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't stop the import", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  const c = state?.counts ?? {};
  const summary = `${c.customers ?? 0} accounts, ${c.orders ?? 0} orders, ${c.newsletter ?? 0} newsletter entries${c.errors ? `, ${c.errors} skipped (bad data)` : ""}`;

  return (
    <Panel className="mt-6">
      <PanelHeader
        title="Import existing shop data"
        description="Brings in the customer accounts, orders and newsletter consent the shop had before the connection was switched on. Safe to run again: nothing is duplicated and staff edits are kept."
        actions={
          state?.status === "running" ? (
            <Pill tone="warning">Running</Pill>
          ) : state?.status === "done" ? (
            <Pill tone="success">Done</Pill>
          ) : state?.status === "failed" ? (
            <Pill tone="danger">Failed</Pill>
          ) : undefined
        }
      />
      <PanelBody className="grid gap-4">
        {!tokenSet && <p className="text-sm text-muted">Save the shop API token above first.</p>}
        {state && state.status !== "idle" && (
          <p role="status" className="text-sm">
            {state.status === "running" && `Importing ${PHASE[state.phase]}… `}
            {summary}.
            {state.finished_at && ` Finished ${formatDateTime(state.finished_at)}.`}
            {state.error && <span className="block text-danger">{state.error}</span>}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="secondary" disabled={!tokenSet || testing} onClick={() => void runTest()}>
            {testing ? "Testing…" : "Test connection"}
          </Button>
          {state?.status === "running" ? (
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => void cancel()}>
              Stop import
            </Button>
          ) : (
            <Button size="sm" disabled={!tokenSet || busy} onClick={() => setConfirming(true)}>
              {state?.status === "done" ? "Import again" : "Start import"}
            </Button>
          )}
        </div>
        {test && (
          <p role="status" className={`text-sm ${test.ok ? "text-success" : "text-danger"}`}>
            {test.detail}
          </p>
        )}
      </PanelBody>
      <ConfirmDialog
        open={confirming}
        title="Import existing shop data?"
        message="Customers are matched by shop account and email; new ones are created with source Shop. Order totals and consent are updated. It runs in the background and you can stop it."
        confirmLabel="Start import"
        tone="primary"
        busy={busy}
        onConfirm={() => void start()}
        onCancel={() => setConfirming(false)}
      />
    </Panel>
  );
}
