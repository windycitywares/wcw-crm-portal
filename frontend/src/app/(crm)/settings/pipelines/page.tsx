"use client";

import { PipelineSettings } from "@/modules/sales/PipelineSettings";

/** Admin → Settings → Pipelines. The page itself lives in the sales module with the rest of its API. */
export default function PipelinesPage() {
  return <PipelineSettings />;
}
