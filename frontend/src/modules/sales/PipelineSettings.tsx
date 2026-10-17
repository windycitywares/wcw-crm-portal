"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { COLOR_OPTIONS, ColorTag } from "@/components/ui/ColorTag";
import { Field, Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { salesApi, type DealStage, type Pipeline } from "./api";

type Outcome = "open" | "won" | "lost";

interface StageForm {
  pipeline: Pipeline;
  stage: DealStage | null;
  name: string;
  probability: string;
  color: string;
  outcome: Outcome;
}

interface BoardForm {
  pipeline: Pipeline | null;
  name: string;
}

/** What a stage's flags mean in one word — the direction of the deal when it lands there. */
function outcomeOf(stage: DealStage) {
  return stage.is_won ? "won" : stage.is_lost ? "lost" : "open";
}

/**
 * Admin → Settings → Pipelines: the boards deals move along, and the stages inside them. This is the one
 * place the shape of the sales process is set — the order of the stages, how far along each one counts
 * (its probability), which one wins or loses the deal, and each stage's colour on the board.
 */
export function PipelineSettings() {
  const toast = useToast();
  const [pipelines, setPipelines] = useState<Pipeline[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [boardForm, setBoardForm] = useState<BoardForm | null>(null);
  const [stageForm, setStageForm] = useState<StageForm | null>(null);
  const [removing, setRemoving] = useState<{ kind: "pipeline" | "stage"; pipeline: Pipeline; stage: DealStage | null } | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPipelines(await salesApi.pipelines());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the pipelines");
      setPipelines([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function fail(err: unknown, fallback: string) {
    toast.push({ tone: "danger", title: fallback, description: err instanceof Error ? err.message : undefined });
  }

  function openBoard(pipeline: Pipeline | null) {
    setBoardForm({ pipeline, name: pipeline?.name ?? "" });
  }

  function openStage(pipeline: Pipeline, stage: DealStage | null) {
    setStageForm({
      pipeline,
      stage,
      name: stage?.name ?? "",
      probability: String(stage?.probability ?? 0),
      color: stage?.color ?? "",
      outcome: stage ? outcomeOf(stage) : "open",
    });
  }

  async function saveBoard(e: React.FormEvent) {
    e.preventDefault();
    if (!boardForm) return;
    const name = boardForm.name.trim();
    if (!name) return;
    setBusy(true);
    try {
      if (boardForm.pipeline) await salesApi.updatePipeline(boardForm.pipeline.id, { name });
      else await salesApi.createPipeline({ name });
      toast.push({ title: boardForm.pipeline ? "Pipeline renamed" : "Pipeline added", description: name });
      setBoardForm(null);
      await load();
    } catch (err) {
      fail(err, "Couldn't save the pipeline");
    } finally {
      setBusy(false);
    }
  }

  async function saveStage(e: React.FormEvent) {
    e.preventDefault();
    if (!stageForm) return;
    const name = stageForm.name.trim();
    if (!name) return;
    const data = {
      name,
      probability: Number(stageForm.probability) || 0,
      color: stageForm.color || null,
      is_won: stageForm.outcome === "won",
      is_lost: stageForm.outcome === "lost",
    };
    setBusy(true);
    try {
      if (stageForm.stage) await salesApi.updateStage(stageForm.pipeline.id, stageForm.stage.id, data);
      else await salesApi.addStage(stageForm.pipeline.id, data);
      toast.push({ title: stageForm.stage ? "Stage saved" : "Stage added", description: name });
      setStageForm(null);
      await load();
    } catch (err) {
      fail(err, "Couldn't save the stage");
    } finally {
      setBusy(false);
    }
  }

  async function makeDefault(pipeline: Pipeline) {
    setBusy(true);
    try {
      await salesApi.updatePipeline(pipeline.id, { is_default: true });
      toast.push({ title: "Default pipeline", description: `${pipeline.name} opens first and the dashboard shows it.` });
      await load();
    } catch (err) {
      fail(err, "Couldn't set the default");
    } finally {
      setBusy(false);
    }
  }

  /** Reordering is a swap of two positions — the board reads stages by (position, id). */
  async function move(pipeline: Pipeline, index: number, delta: number) {
    const stage = pipeline.stages[index];
    const other = pipeline.stages[index + delta];
    if (!stage || !other) return;
    setBusy(true);
    try {
      await salesApi.updateStage(pipeline.id, stage.id, { position: other.position });
      await salesApi.updateStage(pipeline.id, other.id, { position: stage.position });
      await load();
    } catch (err) {
      fail(err, "Couldn't reorder the stages");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!removing) return;
    setBusy(true);
    setRemoveError(null);
    try {
      if (removing.kind === "pipeline") await salesApi.removePipeline(removing.pipeline.id);
      else if (removing.stage) await salesApi.removeStage(removing.pipeline.id, removing.stage.id);
      toast.push({ title: removing.kind === "pipeline" ? "Pipeline deleted" : "Stage deleted" });
      setRemoving(null);
      await load();
    } catch (err) {
      // The API refuses to delete a board or stage that still has open deals — say so where the person is.
      setRemoveError(err instanceof Error ? err.message : "Couldn't delete it");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Pipelines"
        description="The boards deals move along. Each stage says how far along a deal is and which stage wins or loses it."
        actions={
          <Button size="sm" onClick={() => openBoard(null)}>
            New pipeline
          </Button>
        }
      />

      {error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      )}

      {pipelines === null ? (
        <Panel className="px-5 py-6 text-sm text-muted">Loading…</Panel>
      ) : pipelines.length === 0 ? (
        <Panel className="px-5 py-10 text-center text-sm text-muted">
          No pipeline yet. Add one and it gets a starter set of stages you can rename and reorder.
        </Panel>
      ) : (
        <div className="grid gap-5">
          {pipelines.map((pipeline) => (
            <Panel key={pipeline.id}>
              <PanelHeader
                title={pipeline.name}
                description={`${pipeline.stages.length} ${pipeline.stages.length === 1 ? "stage" : "stages"}`}
                actions={
                  <>
                    {pipeline.is_default ? (
                      <Pill dot={false}>Default</Pill>
                    ) : (
                      <Button size="sm" variant="ghost" disabled={busy} onClick={() => void makeDefault(pipeline)}>
                        Make default
                      </Button>
                    )}
                    <Button size="sm" variant="secondary" onClick={() => openBoard(pipeline)}>
                      Rename
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-danger"
                      onClick={() => {
                        setRemoveError(null);
                        setRemoving({ kind: "pipeline", pipeline, stage: null });
                      }}
                    >
                      Delete
                    </Button>
                  </>
                }
              />
              <ul className="divide-y divide-line">
                {pipeline.stages.map((stage, i) => (
                  <li key={stage.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-5 py-3">
                    <ColorTag color={stage.color}>{stage.name}</ColorTag>
                    {stage.is_won && <Pill tone="success">Wins the deal</Pill>}
                    {stage.is_lost && <Pill tone="danger">Loses the deal</Pill>}
                    <span className="num text-xs text-muted">{stage.is_won || stage.is_lost ? "—" : `${stage.probability}%`}</span>
                    <span className="ml-auto flex items-center gap-1">
                      <Button size="sm" variant="ghost" aria-label={`Move ${stage.name} left`} disabled={busy || i === 0} onClick={() => void move(pipeline, i, -1)}>
                        <Icon name="chevronLeft" className="size-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Move ${stage.name} right`}
                        disabled={busy || i === pipeline.stages.length - 1}
                        onClick={() => void move(pipeline, i, 1)}
                      >
                        <Icon name="chevronRight" className="size-4" />
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => openStage(pipeline, stage)}>
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-danger"
                        onClick={() => {
                          setRemoveError(null);
                          setRemoving({ kind: "stage", pipeline, stage });
                        }}
                      >
                        Delete
                      </Button>
                    </span>
                  </li>
                ))}
                <li className="px-5 py-3">
                  <Button size="sm" variant="secondary" onClick={() => openStage(pipeline, null)}>
                    Add stage
                  </Button>
                </li>
              </ul>
            </Panel>
          ))}
        </div>
      )}

      <Modal
        open={boardForm !== null}
        onClose={() => setBoardForm(null)}
        title={boardForm?.pipeline ? "Rename pipeline" : "New pipeline"}
        description={boardForm?.pipeline ? undefined : "A board for a kind of deal — new business, renewals, and so on."}
        size="sm"
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setBoardForm(null)}>
              Cancel
            </Button>
            <Button type="submit" form="pipeline-form" size="sm" disabled={busy}>
              {busy ? "Saving…" : boardForm?.pipeline ? "Save name" : "Add pipeline"}
            </Button>
          </>
        }
      >
        {boardForm && (
          <form id="pipeline-form" onSubmit={saveBoard}>
            <Field label="Name">
              {(p) => <Input {...p} required maxLength={80} autoFocus value={boardForm.name} onChange={(e) => setBoardForm({ ...boardForm, name: e.target.value })} />}
            </Field>
          </form>
        )}
      </Modal>

      <Modal
        open={stageForm !== null}
        onClose={() => setStageForm(null)}
        title={stageForm?.stage ? "Edit stage" : "Add a stage"}
        description={stageForm ? `On ${stageForm.pipeline.name}.` : undefined}
        size="sm"
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setStageForm(null)}>
              Cancel
            </Button>
            <Button type="submit" form="stage-form" size="sm" disabled={busy}>
              {busy ? "Saving…" : stageForm?.stage ? "Save stage" : "Add stage"}
            </Button>
          </>
        }
      >
        {stageForm && (
          <form id="stage-form" onSubmit={saveStage} className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" className="sm:col-span-2">
              {(p) => <Input {...p} required maxLength={80} autoFocus value={stageForm.name} onChange={(e) => setStageForm({ ...stageForm, name: e.target.value })} />}
            </Field>
            <Field label="Probability %" hint="A deal here counts this much in the forecast.">
              {(p) => (
                <Input
                  {...p}
                  type="number"
                  min="0"
                  max="100"
                  value={stageForm.probability}
                  onChange={(e) => setStageForm({ ...stageForm, probability: e.target.value })}
                />
              )}
            </Field>
            <Field label="Colour">
              {(p) => (
                <Select {...p} value={stageForm.color} onChange={(e) => setStageForm({ ...stageForm, color: e.target.value })}>
                  {COLOR_OPTIONS.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field
              label="What landing here means"
              className="sm:col-span-2"
              hint="A stage that wins or loses the deal closes it; normal stages keep it open."
            >
              {(p) => (
                <Select {...p} value={stageForm.outcome} onChange={(e) => setStageForm({ ...stageForm, outcome: e.target.value as Outcome })}>
                  <option value="open">The deal is still open</option>
                  <option value="won">The deal is won</option>
                  <option value="lost">The deal is lost</option>
                </Select>
              )}
            </Field>
          </form>
        )}
      </Modal>

      <ConfirmDialog
        open={removing !== null}
        title={removing?.kind === "pipeline" ? "Delete this pipeline?" : "Delete this stage?"}
        message={
          <>
            {removing?.kind === "pipeline"
              ? `“${removing.pipeline.name}” and its stages will be removed. Boards with open deals can't be deleted.`
              : `“${removing?.stage?.name}” will be removed from ${removing?.pipeline.name}. Stages with open deals can't be deleted.`}
            {removeError && (
              <span className="mt-2 block text-danger" role="alert">
                {removeError}
              </span>
            )}
          </>
        }
        confirmLabel={removing?.kind === "pipeline" ? "Delete pipeline" : "Delete stage"}
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => {
          setRemoving(null);
          setRemoveError(null);
        }}
      />
    </>
  );
}
