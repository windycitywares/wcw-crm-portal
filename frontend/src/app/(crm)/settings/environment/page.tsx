"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";

interface Environment {
  mode: "live" | "test";
  effective: "live" | "test";
  test_exists: boolean;
  test_synced_at: string | null;
  test_mail_to: string | null;
  test_size_bytes: number | null;
  out_of_date: boolean;
  changed_at: string | null;
  changed_by_email: string | null;
}

const size = (bytes: number | null) => (bytes == null ? "—" : bytes > 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(bytes / 1e6))} MB`);

export default function EnvironmentPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [env, setEnv] = useState<Environment | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState<"test" | "live" | "sync" | "delete" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<Environment>("/settings/environment");
      setEnv(data);
    } catch (e) {
      toast.push({ title: "Couldn't load", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { void load(); }, [load]);

  const switchMode = async (mode: "live" | "test") => {
    setConfirm(null);
    setLoading(true);
    try {
      await apiFetch(`/settings/environment/mode?mode=${mode}`, { method: "PUT" });
      toast.push({ title: mode === "test" ? "Switched to test mode" : "Switched to live data" });
      await load();
    } catch (e) {
      toast.push({ title: "Couldn't switch", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setLoading(false);
    }
  };

  const sync = async () => {
    setConfirm(null);
    setLoading(true);
    try {
      await apiFetch("/settings/environment/sync", { method: "POST" });
      toast.push({ title: "Test data refreshed" });
      await load();
    } catch (e) {
      toast.push({ title: "Couldn't sync", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setLoading(false);
    }
  };

  const deleteCopy = async () => {
    setConfirm(null);
    setLoading(true);
    try {
      await apiFetch("/settings/environment/test-data", { method: "DELETE" });
      toast.push({ title: "Test data deleted" });
      await load();
    } catch (e) {
      toast.push({ title: "Couldn't delete", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setLoading(false);
    }
  };

  if (!can("settings:manage")) return <PageHeader title="Test mode" description="You don't have permission to manage test mode." />;

  return (
    <div>
      <PageHeader title="Test mode" description="Work on a copy of the live data without touching the real thing." />

      {loading && !env && <p className="text-sm text-muted">Loading…</p>}

      {env && (
        <>
          <Panel className="mb-4">
            <PanelHeader title="Current mode" />
            <PanelBody className="flex flex-wrap items-center gap-3">
              <Pill tone={env.effective === "test" ? "warning" : "success"}>{env.effective === "test" ? "Test" : "Live"}</Pill>
              <span className="text-sm text-muted">
                {env.effective === "test" ? "Working on the test copy." : "Working on live data."}
              </span>
              {env.out_of_date && <Pill tone="danger">Test copy is out of date</Pill>}
            </PanelBody>
          </Panel>

          <Panel className="mb-4">
            <PanelHeader title="Test data" description="A copy of the live data. Switching to test copies it fresh." />
            <PanelBody className="space-y-3">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span>Exists: <strong>{env.test_exists ? "yes" : "no"}</strong></span>
                <span>Size: <strong>{size(env.test_size_bytes)}</strong></span>
                {env.test_synced_at && <span>Synced: <strong>{new Date(env.test_synced_at).toLocaleString()}</strong></span>}
                {env.changed_by_email && <span>Changed by: <strong>{env.changed_by_email}</strong></span>}
              </div>
              <div className="flex flex-wrap gap-2">
                {env.effective === "live" && (
                  <Button size="sm" onClick={() => setConfirm("test")}>Switch to test</Button>
                )}
                {env.effective === "test" && (
                  <Button size="sm" onClick={() => setConfirm("live")}>Switch to live</Button>
                )}
                {env.test_exists && (
                  <>
                    <Button size="sm" variant="secondary" onClick={() => setConfirm("sync")}>Re-copy live data</Button>
                    {env.effective === "live" && (
                      <Button size="sm" variant="secondary" onClick={() => setConfirm("delete")}>Delete test data</Button>
                    )}
                  </>
                )}
              </div>
            </PanelBody>
          </Panel>

          {/* Confirm dialogs */}
          {confirm === "test" && (
            <div className="fixed inset-0 z-50 grid place-items-center bg-night/55 p-4">
              <div className="w-full max-w-md rounded-[var(--radius-card)] border border-line bg-surface p-6 shadow-xl">
                <h3 className="text-base font-semibold">Switch to test mode?</h3>
                <p className="mt-2 text-sm text-muted">The live data is copied and the whole CRM works on the copy until you switch back. Everyone is signed out and signs in again.</p>
                <div className="mt-4 flex justify-end gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setConfirm(null)}>Cancel</Button>
                  <Button size="sm" onClick={switchMode.bind(null, "test")}>Switch to test</Button>
                </div>
              </div>
            </div>
          )}
          {confirm === "live" && (
            <div className="fixed inset-0 z-50 grid place-items-center bg-night/55 p-4">
              <div className="w-full max-w-md rounded-[var(--radius-card)] border border-line bg-surface p-6 shadow-xl">
                <h3 className="text-base font-semibold">Switch back to live data?</h3>
                <p className="mt-2 text-sm text-muted">The CRM goes back to the real data. The test copy is kept until you delete it.</p>
                <div className="mt-4 flex justify-end gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setConfirm(null)}>Cancel</Button>
                  <Button size="sm" onClick={switchMode.bind(null, "live")}>Switch to live</Button>
                </div>
              </div>
            </div>
          )}
          {confirm === "sync" && (
            <div className="fixed inset-0 z-50 grid place-items-center bg-night/55 p-4">
              <div className="w-full max-w-md rounded-[var(--radius-card)] border border-line bg-surface p-6 shadow-xl">
                <h3 className="text-base font-semibold">Copy the live data again?</h3>
                <p className="mt-2 text-sm text-muted">Everything done during testing is replaced by a fresh copy of the live data. This can't be undone.</p>
                <div className="mt-4 flex justify-end gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setConfirm(null)}>Cancel</Button>
                  <Button size="sm" variant="secondary" onClick={sync}>Re-copy</Button>
                </div>
              </div>
            </div>
          )}
          {confirm === "delete" && (
            <div className="fixed inset-0 z-50 grid place-items-center bg-night/55 p-4">
              <div className="w-full max-w-md rounded-[var(--radius-card)] border border-line bg-surface p-6 shadow-xl">
                <h3 className="text-base font-semibold">Delete the test data?</h3>
                <p className="mt-2 text-sm text-muted">The test copy and everything testers did in it are removed. The live data isn't touched.</p>
                <div className="mt-4 flex justify-end gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setConfirm(null)}>Cancel</Button>
                  <Button size="sm" onClick={deleteCopy}>Delete</Button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
