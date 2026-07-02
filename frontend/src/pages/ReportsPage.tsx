import { useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { ComplianceReport, ScanRun } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, Section } from "../components/Primitives";
import { formatDate } from "../utils/format";

export function ReportsPage() {
  const reports = useResource(api.reports.list);
  const scanRuns = useResource(api.scanRuns.list);
  const [scanRunId, setScanRunId] = useState("");

  async function create(type: "engineering" | "leadership") {
    if (!scanRunId) return;
    await api.reports.create(type, Number(scanRunId));
    await reports.reload();
  }

  return (
    <Section
      title="Reports"
      actions={<ReportActions scanRuns={scanRuns.data || []} scanRunId={scanRunId} setScanRunId={setScanRunId} onCreate={create} />}
    >
      <ResourceBoundary resource={reports}>
        {(data) => <ReportTable data={data} />}
      </ResourceBoundary>
    </Section>
  );
}

function ReportActions({
  scanRuns,
  scanRunId,
  setScanRunId,
  onCreate,
}: {
  scanRuns: ScanRun[];
  scanRunId: string;
  setScanRunId: (value: string) => void;
  onCreate: (type: "engineering" | "leadership") => void;
}) {
  return (
    <>
      <select className="control" value={scanRunId} onChange={(event) => setScanRunId(event.target.value)}>
        <option value="">Scan run</option>
        {scanRuns.map((scanRun) => (
          <option key={scanRun.id} value={scanRun.id}>
            {scanRun.id} {scanRun.target_environment}
          </option>
        ))}
      </select>
      <button className="icon-button" disabled={!scanRunId} onClick={() => onCreate("engineering")}>
        Engineering
      </button>
      <button className="icon-button" disabled={!scanRunId} onClick={() => onCreate("leadership")}>
        Leadership
      </button>
    </>
  );
}

function ReportTable({ data }: { data: ComplianceReport[] }) {
  return (
    <DataTable
      columns={["ID", "Scan Run", "Type", "Generated", "Hash", "Download"]}
      rows={data.map((report) => [
        report.id,
        report.scan_run_id,
        report.report_type,
        formatDate(report.generated_at),
        report.content_hash || "n/a",
        <a className="icon-button" href={api.reports.downloadUrl(report.id)}>
          Download
        </a>,
      ])}
    />
  );
}
