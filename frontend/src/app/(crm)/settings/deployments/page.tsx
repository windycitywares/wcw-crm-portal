"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDateTime, timeAgo } from "@/lib/utils";
import { deployApi, errorText, type DeployMode, type DeployStatus } from "@/modules/settings/api";

const MODE_LABEL: Record<DeployMode, string> = {
  auto: "Automatic",
  schedule: "At set times",
  paused: "Paused",
};

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 gap-y-0.5 py-2 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 text-right">{children}</dd>
    </div>
  );
}

export default function DeploymentsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState<DeployStatus | null>(null);
  const [log, setLog] = useState("");
  const [mode, setMode] = useState<DeployMode>("auto");
  const [interval, setIntervalMinutes] = useState(10);
  const [times, setTimes] = useState<string[]>([]);
  const [newTime, setNewTime] = useState("02:00");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);
  const allowed = can("settings:manage");

  const refresh = useCallback(
    async (withForm = false) => {
      try {
        const [s, l] = await Promise.all([deployApi.status(), deployApi.log(200)]);
        setStatus(s);
        setLog(l.log);
        if (withForm) {
          setMode(s.mode);
          setIntervalMinutes(s.interval_minutes);
          setTimes(s.schedule_times);
        }
      } catch (err) {
        toast.push({ tone: "danger", title: "Couldn't load deployments", description: errorText(err) });
      }
    },
    [toast],
  );

  useEffect(() => {
    if (allowed) void refresh(true);
  }, [allowed, refresh]);

  // Poll while something is queued or running, so the page shows progress without reloading.
  const active = !!status && (status.running || !!status.requested_at);
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(t);
  }, [active, refresh]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [log]);

  if (!allowed) return <PageHeader title="Deployments" description="Only admins can manage deployments." />;
  if (!status) return <PageHeader title="Deployments" description="Loading…" />;

  async function act(fn: () => Promise<DeployStatus>, title: string, description?: string) {
    setBusy(true);
    try {
      setStatus(await fn());
      toast.push({ title, description });
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save", description: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  const save = () =>
    act(() => deployApi.configure({ mode, interval_minutes: interval, schedule_times: times }), "Update settings saved", MODE_LABEL[mode]);

  const state = status.running ? (
    <Pill tone="info">Deploying…</Pill>
  ) : status.requested_at ? (
    <Pill tone="accent">Queued</Pill>
  ) : status.mode === "paused" ? (
    <Pill tone="warning">Paused</Pill>
  ) : (
    <Pill tone="success">{MODE_LABEL[status.mode]}</Pill>
  );

  return (
    <>
      <PageHeader
        title="Deployments"
        description="Merged changes on GitHub go live here. Deploy now, pause updates, or choose when they happen."
        actions={
          <>
            {state}
            {status.requested_at ? (
              <Button size="sm" variant="secondary" disabled={busy || status.running} onClick={() => void act(deployApi.cancel, "Deploy cancelled")}>
                Cancel
              </Button>
            ) : (
              <Button
                size="sm"
                disabled={busy || status.running}
                onClick={() => void act(deployApi.now, "Deploy queued", "Starts within a minute; the log below updates as it runs.")}
              >
                <Icon name="download" className="size-4" />
                Deploy now
              </Button>
            )}
          </>
        }
      />

      {!status.cron_seen && (
        <p role="alert" className="mb-6 rounded-[var(--radius-control)] border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          The server hasn&apos;t checked in during the last few minutes. Make sure the cron job runs every minute (see the deployment guide); until then
          “Deploy now” waits for the next check.
        </p>
      )}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-2">
        <Panel>
          <PanelHeader title="What's live" />
          <PanelBody>
            <dl className="divide-y divide-line">
              <Row label="API">
                {status.api.commit ? (
                  <>
                    <span className="font-mono">{status.api.commit}</span> {status.api.subject}
                    {status.api.date && <span className="block text-xs text-muted">{formatDateTime(status.api.date)}</span>}
                  </>
                ) : (
                  "—"
                )}
              </Row>
              <Row label="Web app build">{status.web_build ? <span className="font-mono">{status.web_build}</span> : "—"}</Row>
              <Row label="Last check for updates">
                {status.last_check_at ? `${timeAgo(status.last_check_at)}${status.last_reason ? ` (${status.last_reason})` : ""}` : "Never"}
              </Row>
              <Row label="Last result">{status.last_result ?? "—"}</Row>
              {status.requested_at && (
                <Row label="Queued">
                  {timeAgo(status.requested_at)}
                  {status.requested_by ? ` by ${status.requested_by}` : ""}
                </Row>
              )}
            </dl>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="When to update" description={`Times are in ${status.timezone} (Settings → Business hours).`} />
          <PanelBody className="grid gap-4">
            <fieldset className="grid gap-2 text-sm">
              <legend className="mb-1 font-medium">Updates</legend>
              {(["auto", "schedule", "paused"] as DeployMode[]).map((m) => (
                <label key={m} className="flex items-start gap-3">
                  <input type="radio" name="mode" className="mt-0.5 size-4 accent-[var(--color-accent)]" checked={mode === m} onChange={() => setMode(m)} />
                  <span>
                    <span className="font-medium">{MODE_LABEL[m]}</span>
                    <span className="block text-muted">
                      {m === "auto" && "Check GitHub regularly and install anything new."}
                      {m === "schedule" && "Only install updates at the times below (e.g. overnight)."}
                      {m === "paused" && "Never install automatically. “Deploy now” still works."}
                    </span>
                  </span>
                </label>
              ))}
            </fieldset>
            {mode === "auto" && (
              <Field label="Check every (minutes)" className="max-w-40">
                {(p) => (
                  <Select {...p} value={interval} onChange={(e) => setIntervalMinutes(Number(e.target.value))}>
                    {[1, 5, 10, 15, 30, 60, 120, 240].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
            {mode === "schedule" && (
              <div className="grid gap-2">
                <div className="flex flex-wrap items-end gap-2">
                  <Field label="Add a time">{(p) => <Input {...p} type="time" value={newTime} onChange={(e) => setNewTime(e.target.value)} />}</Field>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={!newTime || times.includes(newTime)}
                    onClick={() => setTimes([...times, newTime].sort())}
                  >
                    <Icon name="plus" className="size-4" />
                    Add time
                  </Button>
                </div>
                <ul className="flex flex-wrap gap-2" aria-label="Update times">
                  {times.map((t) => (
                    <li key={t} className="inline-flex items-center gap-1 rounded-full bg-sand py-0.5 pl-3 pr-1 text-sm">
                      {t}
                      <button type="button" onClick={() => setTimes(times.filter((x) => x !== t))} className="grid size-6 place-items-center rounded-full hover:bg-line">
                        <Icon name="close" className="size-3.5" />
                        <span className="sr-only">Remove {t}</span>
                      </button>
                    </li>
                  ))}
                  {times.length === 0 && <li className="text-sm text-muted">No times yet.</li>}
                </ul>
              </div>
            )}
            <div>
              <Button size="sm" onClick={() => void save()} disabled={busy || (mode === "schedule" && times.length === 0)}>
                Save update settings
              </Button>
            </div>
          </PanelBody>
        </Panel>
      </div>

      <Panel className="mt-6">
        <PanelHeader
          title="Deploy log"
          description="Latest lines from the server."
          actions={
            <Button size="sm" variant="ghost" onClick={() => void refresh()}>
              Refresh
            </Button>
          }
        />
        <pre ref={logRef} className="max-h-[28rem] overflow-auto whitespace-pre-wrap break-words bg-night px-5 py-4 font-mono text-xs leading-relaxed text-night-muted" tabIndex={0} aria-label="Deploy log">
          {log || "No log yet."}
        </pre>
      </Panel>
    </>
  );
}
