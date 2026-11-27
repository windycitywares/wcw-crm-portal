"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { TOPICS } from "@/modules/help/content";
import { helpApi, type FeedbackRow, type TopicSummary } from "@/modules/help/api";

const titleOf = (id: string) => TOPICS.find((t) => t.id === id)?.title ?? id;

export default function HelpFeedbackPage() {
  const { can } = useAuth();
  const toast = useToast();
  const allowed = can("settings:manage");
  const [summary, setSummary] = useState<TopicSummary[] | null>(null);
  const [topic, setTopic] = useState<string | null>(null);
  const [onlyNo, setOnlyNo] = useState(true);
  const [rows, setRows] = useState<FeedbackRow[] | null>(null);

  useEffect(() => {
    if (!allowed) return;
    helpApi.summary().then(setSummary).catch((e) => toast.push({ tone: "danger", title: "Couldn't load the feedback", description: e instanceof Error ? e.message : undefined }));
  }, [allowed, toast]);

  const loadRows = useCallback(async () => {
    if (!topic) return;
    setRows(null);
    try {
      setRows(await helpApi.list({ topic_id: topic, helpful: onlyNo ? false : undefined, limit: 100 }));
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't load the answers", description: e instanceof Error ? e.message : undefined });
    }
  }, [topic, onlyNo, toast]);
  useEffect(() => { void loadRows(); }, [loadRows]);

  if (!allowed) return <PageHeader title="Help feedback" description="You don't have access to this page." />;

  const columns: Column<TopicSummary>[] = [
    { key: "guide", header: "Guide", cell: (r) => <span className="font-medium">{titleOf(r.topic_id)}</span> },
    { key: "yes", header: "Helpful", align: "right", cell: (r) => <span className="num">{r.helpful}</span> },
    { key: "no", header: "Not helpful", align: "right", cell: (r) => (r.not_helpful ? <Badge variant="warning">{r.not_helpful}</Badge> : <span className="num text-muted">0</span>) },
    { key: "last", header: "Last answer", hide: "sm", cell: (r) => <span className="num whitespace-nowrap text-muted">{formatDateTime(r.last_at)}</span> },
    { key: "show", header: <span className="sr-only">Answers</span>, align: "right", cell: (r) => (
      <Button size="sm" variant={topic === r.topic_id ? "secondary" : "ghost"} onClick={() => setTopic(r.topic_id)}>Show answers</Button>
    ) },
  ];
  const answers: Column<FeedbackRow>[] = [
    { key: "at", header: "When", cell: (r) => <span className="num whitespace-nowrap text-muted">{formatDateTime(r.created_at)}</span> },
    { key: "who", header: "Who", hide: "sm", cell: (r) => r.user_name ?? <span className="text-muted">Unknown</span> },
    { key: "vote", header: "Answer", cell: (r) => (r.helpful ? <Badge variant="success">Helpful</Badge> : <Badge variant="warning">Not helpful</Badge>) },
    { key: "comment", header: "Comment", cell: (r) => r.comment ?? <span className="text-muted">No comment</span> },
  ];

  return (
    <div className="space-y-5">
      <PageHeader title="Help feedback" description="What people said when asked “Was this helpful?” The guides people found least helpful come first." />
      <Panel>
        <DataTable columns={columns} rows={summary} rowKey={(r) => r.topic_id} caption="Feedback per guide"
          empty={<p className="px-5 py-8 text-center text-sm text-muted">No feedback yet. It appears here once people answer at the end of a guide.</p>} />
      </Panel>
      {topic && (
        <Panel>
          <PanelHeader title={titleOf(topic)} description="Answers for this guide, newest first."
            actions={<Button size="sm" variant="secondary" onClick={() => setOnlyNo(!onlyNo)}>{onlyNo ? "Show all answers" : "Only not helpful"}</Button>} />
          <DataTable columns={answers} rows={rows} rowKey={(r) => r.id} caption={`Answers for ${titleOf(topic)}`}
            empty={<p className="px-5 py-8 text-center text-sm text-muted">No answers to show.</p>} />
        </Panel>
      )}
    </div>
  );
}
