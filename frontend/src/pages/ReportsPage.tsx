import { useState } from "react";
import { Loader2 } from "lucide-react";
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
  const [creating, setCreating] = useState<"engineering" | "leadership" | null>(null);

  async function create(type: "engineering" | "leadership") {
    if (!scanRunId || creating) return;
    setCreating(type);
    try {
      await api.reports.create(type, Number(scanRunId));
      await reports.reload();
    } finally {
      setCreating(null);
    }
  }

  return (
    <Section
      title="Reports"
      description="Generate engineering and leadership reports"
      actions={
        <ReportActions
          creating={creating}
          scanRuns={scanRuns.data || []}
          scanRunId={scanRunId}
          setScanRunId={setScanRunId}
          onCreate={create}
        />
      }
    >
      <ResourceBoundary resource={reports}>
        {(data) => <ReportTable data={data} />}
      </ResourceBoundary>
    </Section>
  );
}

function ReportActions({
  creating,
  scanRuns,
  scanRunId,
  setScanRunId,
  onCreate,
}: {
  creating: "engineering" | "leadership" | null;
  scanRuns: ScanRun[];
  scanRunId: string;
  setScanRunId: (value: string) => void;
  onCreate: (type: "engineering" | "leadership") => void;
}) {
  return (
    <>
      <select className="control" disabled={Boolean(creating)} value={scanRunId} onChange={(event) => setScanRunId(event.target.value)}>
        <option value="">Scan run</option>
        {scanRuns.map((scanRun) => (
          <option key={scanRun.id} value={scanRun.id}>
            {scanRun.id} {scanRun.target_environment}
          </option>
        ))}
      </select>
      <button className="icon-button" disabled={!scanRunId || Boolean(creating)} onClick={() => onCreate("engineering")}>
        {creating === "engineering" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
        {creating === "engineering" ? "Generating..." : "Engineering"}
      </button>
      <button className="icon-button" disabled={!scanRunId || Boolean(creating)} onClick={() => onCreate("leadership")}>
        {creating === "leadership" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
        {creating === "leadership" ? "Generating..." : "Leadership"}
      </button>
    </>
  );
}

function ReportTable({ data }: { data: ComplianceReport[] }) {
  return (
    <DataTable
      columns={["ID", "Scan Run", "Type", "Generated", "Download"]}
      rows={data.map((report) => [
        report.id,
        report.scan_run_id,
        report.report_type,
        formatDate(report.generated_at),
        <a key={`dl-${report.id}`} className="icon-button" href={api.reports.downloadUrl(report.id)}>
          Download
        </a>,
      ])}
    />
  );
}
