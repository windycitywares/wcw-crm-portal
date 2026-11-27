"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { cn } from "@/lib/utils";
import { helpApi } from "./api";

/** "Was this helpful?" at the end of a guide. A thumbs up is sent straight away; a thumbs down asks what was missing or confusing. */
export function Feedback({ topicId, page }: { topicId: string; page: string }) {
  const [answer, setAnswer] = useState<"up" | "down" | null>(null);
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "failed">("idle");

  useEffect(() => { setAnswer(null); setComment(""); setState("idle"); }, [topicId]);

  async function send(helpful: boolean, text?: string) {
    setState("sending");
    try {
      await helpApi.send({ topic_id: topicId, page, helpful, comment: text?.trim() || undefined });
      setState("sent");
    } catch {
      setState("failed");
    }
  }

  if (state === "sent") {
    return <p role="status" className="mt-8 border-t border-line pt-4 text-sm text-muted">Thank you. {answer === "down" ? "We will use this to improve the guide." : "Glad it helped."}</p>;
  }
  return (
    <div className="mt-8 border-t border-line pt-4">
      <p id={`fb-${topicId}`} className="text-sm font-semibold text-ink">Was this helpful?</p>
      <div role="group" aria-labelledby={`fb-${topicId}`} className="mt-2 flex gap-2">
        {([["up", "thumbsUp", "Yes"], ["down", "thumbsDown", "No"]] as const).map(([k, icon, label]) => (
          <button key={k} type="button" aria-pressed={answer === k} disabled={state === "sending"}
            onClick={() => { setAnswer(k); if (k === "up") void send(true); }}
            className={cn("inline-flex h-9 items-center gap-1.5 rounded-[var(--radius-control)] border px-3 text-sm font-medium hover:border-accent disabled:opacity-60",
              answer === k ? "border-accent bg-accent/5 text-accent" : "border-line text-ink")}>
            <Icon name={icon} className="size-4" />
            {label}
          </button>
        ))}
      </div>
      {answer === "down" && (
        <form className="mt-3 space-y-2" onSubmit={(e) => { e.preventDefault(); void send(false, comment); }}>
          <Field label="What was missing or confusing?" hint="Optional. Please don't include passwords or other secrets.">
            {(p) => <Textarea {...p} rows={3} maxLength={1000} value={comment} onChange={(e) => setComment(e.target.value)} />}
          </Field>
          <Button type="submit" size="sm" loading={state === "sending"}>Send feedback</Button>
        </form>
      )}
      {state === "failed" && <p role="alert" className="mt-2 text-xs font-medium text-danger">Couldn't send that. Please try again.</p>}
    </div>
  );
}
