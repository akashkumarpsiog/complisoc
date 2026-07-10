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
  const [cooldowns, setCooldowns] = useState<Record<string, number>>({});

  async function create(type: "engineering" | "leadership") {
    const key = `${scanRunId}:${type}`;
    if (!scanRunId || creating || Date.now() < (cooldowns[key] || 0)) return;
    setCreating(type);
    try {
      await api.reports.create(type, Number(scanRunId));
      setCooldowns((prev) => ({ ...prev, [key]: Date.now() + 5000 }));
      await reports.reload();
    } finally {
      setCreating(null);
    }
  }

  return (
    <Section
      title="Reports"
      actions={
        <ReportActions
          cooldowns={cooldowns}
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
  cooldowns,
  creating,
  scanRuns,
  scanRunId,
  setScanRunId,
  onCreate,
}: {
  cooldowns: Record<string, number>;
  creating: "engineering" | "leadership" | null;
  scanRuns: ScanRun[];
  scanRunId: string;
  setScanRunId: (value: string) => void;
  onCreate: (type: "engineering" | "leadership") => void;
}) {
  const engineeringCooling = Date.now() < (cooldowns[`${scanRunId}:engineering`] || 0);
  const leadershipCooling = Date.now() < (cooldowns[`${scanRunId}:leadership`] || 0);
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
      <button className="icon-button" disabled={!scanRunId || Boolean(creating) || engineeringCooling} onClick={() => onCreate("engineering")}>
        {creating === "engineering" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
        {creating === "engineering" ? "Generating..." : "Engineering"}
      </button>
      <button className="icon-button" disabled={!scanRunId || Boolean(creating) || leadershipCooling} onClick={() => onCreate("leadership")}>
        {creating === "leadership" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
        {creating === "leadership" ? "Generating..." : "Leadership"}
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
