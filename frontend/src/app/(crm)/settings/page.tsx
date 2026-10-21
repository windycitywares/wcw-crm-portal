"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody } from "@/components/ui/Panel";

export default function SettingsHome() {
  return (
    <div>
      <PageHeader
        title="Settings"
        description="Everything the CRM runs on: the team, the lists you pick from, email, hours and integrations."
      />
      <Panel>
        <PanelBody className="text-sm text-muted">
          Choose a section from the list to edit it. Every change is recorded in the audit log.
        </PanelBody>
      </Panel>
    </div>
  );
}
