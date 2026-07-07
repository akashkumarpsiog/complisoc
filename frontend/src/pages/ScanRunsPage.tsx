import { useEffect, useState } from "react";
import { ListFilter } from "lucide-react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { ScanRun, ScanRunSummary } from "../types";
import { Detail } from "../components/Detail";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, EmptyState, LoadingState, MetricCard, Section, StatusBadge } from "../components/Primitives";
import { formatDate } from "../utils/format";
import { ScanRunCreator } from "../components/ScanRunCreator";

export function ScanRunsPage() {
  const scanRuns = useResource(api.scanRuns.list);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = scanRuns.data?.find((item) => item.id === selectedId) || null;

  return (
    <div className="grid gap-5 2xl:grid-cols-[1fr_420px]">
      <Section title="Scan Runs" actions={<ScanRunCreator onCreated={scanRuns.reload} />}>
        <ResourceBoundary resource={scanRuns}>
          {(data) => <ScanRunTable data={data} onSelect={setSelectedId} />}
        </ResourceBoundary>
      </Section>
      <ScanRunDetail scanRun={selected} />
    </div>
  );
}

function ScanRunTable({ data, onSelect }: { data: ScanRun[]; onSelect: (id: number) => void }) {
  return (
    <DataTable
      columns={["ID", "Environment", "Status", "Created", "Open"]}
      rows={data.map((scanRun) => [
        scanRun.id,
        scanRun.target_environment,
        <StatusBadge value={scanRun.status} />,
        formatDate(scanRun.created_at),
        <button className="icon-button" onClick={() => onSelect(scanRun.id)}>
          <ListFilter className="h-4 w-4" aria-hidden />
          Detail
        </button>,
      ])}
    />
  );
}

function ScanRunDetail({ scanRun }: { scanRun: ScanRun | null }) {
  const [summary, setSummary] = useState<ScanRunSummary | null>(null);

  useEffect(() => {
    if (!scanRun) {
      setSummary(null);
      return;
    }
    void api.scanRuns.summary(scanRun.id).then(setSummary);
  }, [scanRun]);

  return (
    <Section title="Scan Run Detail">
      {scanRun ? (
        <div className="space-y-3">
          <Detail label="Scan run" value={scanRun.id} />
          <Detail label="Environment" value={scanRun.target_environment} />
          <Detail label="Status" value={<StatusBadge value={scanRun.status} />} />
          <Detail label="Started" value={formatDate(scanRun.started_at)} />
          {summary ? (
            <div className="grid grid-cols-2 gap-3 pt-2">
              <MetricCard label="Raw" value={summary.raw_findings} />
              <MetricCard label="Normalized" value={summary.normalized_findings} />
              <MetricCard label="Mappings" value={summary.mappings} />
              <MetricCard label="Published" value={summary.published_mappings} />
            </div>
          ) : (
            <LoadingState label="Loading summary" />
          )}
        </div>
      ) : (
        <EmptyState label="Select a scan run." />
      )}
    </Section>
  );
}
