"use client";

import { useState } from "react";
import { ColorTag } from "@/components/ui/ColorTag";
import { useToast } from "@/components/ui/Toast";
import { cn, formatDate } from "@/lib/utils";
import { useDirectory } from "@/modules/records/useDirectory";
import { money, salesApi, type Board, type Deal } from "./api";

/**
 * The pipeline as a kanban: one column per stage, open deals as cards. Drag a card to another column to
 * move it — landing on the won or lost column wins or loses the deal (that is the rule on the server, not
 * a UI trick), and the weighted total follows the stage's probability.
 *
 * Dragging is a mouse shortcut, never the only way: every card opens the deal dialog, where the stage is a
 * picker, so the board can be worked with the keyboard or on a touch screen.
 */
export function DealBoard({
  board,
  canMove,
  onEdit,
  onChanged,
}: {
  board: Board | null;
  /** Whether this person may move this deal (their own, or a manager's any). */
  canMove: (deal: Deal) => boolean;
  onEdit: (deal: Deal) => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const { name } = useDirectory();
  const [dragging, setDragging] = useState<Deal | null>(null);
  const [over, setOver] = useState<number | null>(null);

  async function drop(stageId: number) {
    const deal = dragging;
    setDragging(null);
    setOver(null);
    if (!deal || deal.stage_id === stageId) return;
    try {
      const moved = await salesApi.updateDeal(deal.id, { stage_id: stageId });
      const where = board?.stages.find((c) => c.stage.id === stageId)?.stage;
      toast.push({
        title: moved.status === "won" ? "Deal won" : moved.status === "lost" ? "Deal lost" : "Deal moved",
        description: where ? `“${moved.title}” is now in ${where.name}.` : moved.title,
      });
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't move the deal", description: err instanceof Error ? err.message : undefined });
    } finally {
      onChanged();
    }
  }

  if (!board) return <p className="px-5 py-6 text-sm text-muted">Loading the board…</p>;

  return (
    <div className="flex gap-4 overflow-x-auto p-5">
      {board.stages.map((column) => {
        const { stage } = column;
        return (
          <section
            key={stage.id}
            aria-label={`${stage.name}: ${column.deals.length} open`}
            onDragOver={(e) => {
              if (!dragging) return;
              e.preventDefault();
              setOver(stage.id);
            }}
            onDragLeave={() => setOver((id) => (id === stage.id ? null : id))}
            onDrop={(e) => {
              e.preventDefault();
              void drop(stage.id);
            }}
            className={cn(
              "flex w-72 shrink-0 flex-col rounded-[var(--radius-card)] border bg-canvas/60 transition-colors",
              over === stage.id ? "border-accent bg-accent-soft/40" : "border-line",
            )}
          >
            <header className="border-b border-line px-3 py-2.5">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <ColorTag color={stage.color}>{stage.name}</ColorTag>
                <span className="num text-xs text-muted">{column.deals.length}</span>
                <span className="num ml-auto text-sm font-medium">{money(column.total_value)}</span>
              </div>
              <p className="num mt-1 text-xs text-muted">
                {money(column.weighted_value)} weighted ·{" "}
                {stage.is_won ? "wins the deal" : stage.is_lost ? "loses the deal" : `${stage.probability}%`}
              </p>
            </header>
            <ul className="flex flex-1 flex-col gap-2 p-2">
              {column.deals.map((deal) => (
                <li key={deal.id}>
                  <button
                    type="button"
                    draggable={canMove(deal)}
                    onDragStart={() => setDragging(deal)}
                    onDragEnd={() => {
                      setDragging(null);
                      setOver(null);
                    }}
                    onClick={() => onEdit(deal)}
                    title={canMove(deal) ? "Drag to another stage, or click to edit" : "Click to view"}
                    className={cn(
                      "w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 py-2 text-left text-sm transition-colors hover:border-ink/30 focus-visible:outline-2 focus-visible:outline-accent",
                      canMove(deal) && "cursor-grab active:cursor-grabbing",
                      dragging?.id === deal.id && "opacity-50",
                    )}
                  >
                    <span className="block truncate font-medium">{deal.title}</span>
                    {deal.customer_name && <span className="block truncate text-xs text-muted">{deal.customer_name}</span>}
                    <span className="mt-1 flex items-baseline justify-between gap-2">
                      <span className="num text-sm">{money(deal.value, deal.currency)}</span>
                      <span className="num text-xs text-muted">{deal.expected_close_on ? formatDate(deal.expected_close_on) : "No date"}</span>
                    </span>
                    <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted">
                      <span className="truncate">{name(deal.owner_id)}</span>
                      {deal.probability !== stage.probability && <span className="num">{deal.probability}%</span>}
                    </span>
                  </button>
                </li>
              ))}
              {column.deals.length === 0 && (
                <li className="grid flex-1 place-items-center rounded-[var(--radius-control)] border border-dashed border-line px-3 py-6 text-center text-xs text-muted">
                  {dragging
                    ? stage.is_won
                      ? "Drop to win it"
                      : stage.is_lost
                        ? "Drop to lose it"
                        : "Drop here"
                    : "No open deals"}
                </li>
              )}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
