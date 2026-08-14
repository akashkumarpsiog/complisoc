import { useEffect, useState } from "react";
import { Archive, ArrowRight, RotateCcw } from "lucide-react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { ScanRun, ScanRunSummary } from "../types";
import { Detail } from "../components/Detail";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, EmptyState, LoadingState, MetricCard, Section, StatusBadge } from "../components/Primitives";
import { formatDate } from "../utils/format";
import { ScanRunCreator } from "../components/ScanRunCreator";

export function ScanRunsPage({ onSelectScan }: { onSelectScan: (id: number) => void }) {
  const [showArchived, setShowArchived] = useState(false);
  const scanRuns = useResource(() => api.scanRuns.list(showArchived), [showArchived]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = scanRuns.data?.find((item) => item.id === selectedId) || null;
  const [summary, setSummary] = useState<ScanRunSummary | null>(null);

  useEffect(() => {
    if (!selected) {
      setSummary(null);
      return;
    }
    void api.scanRuns.summary(selected.id).then(setSummary);
  }, [selected]);

  return (
    <div className="grid gap-5 2xl:grid-cols-[1fr_420px]">
      <Section title="Scan Runs" description={showArchived ? "Archived scan history only. Restore a scan to return it to active views." : "Active scans only. Archived scans remain available for audit."} actions={<><button className="secondary-button" onClick={() => setShowArchived((value) => !value)}>{showArchived ? "Show active" : "Show archived"}</button><ScanRunCreator onCreated={scanRuns.reload} /></>}>
        <ResourceBoundary resource={scanRuns}>
          {(data) => <ScanRunTable data={data} onSelect={setSelectedId} onOpen={onSelectScan} onChanged={scanRuns.reload} />}
        </ResourceBoundary>
      </Section>
      <ScanRunDetail scanRun={selected} summary={summary} onOpen={onSelectScan} />
    </div>
  );
}

function ScanRunTable({ data, onSelect, onOpen, onChanged }: { data: ScanRun[]; onSelect: (id: number) => void; onOpen: (id: number) => void; onChanged: () => Promise<void> }) {
  return (
    <DataTable
      columns={["ID", "Environment", "Status", "Created", "Open", "Retention"]}
      rows={data.map((scanRun) => [
        scanRun.id,
        scanRun.target_environment,
        <StatusBadge value={scanRun.status} />,
        formatDate(scanRun.created_at),
        <button className="primary-button" onClick={() => onOpen(scanRun.id)}>
          <ArrowRight className="h-4 w-4" aria-hidden />
          View
        </button>,
        <button className="secondary-button" onClick={() => void (scanRun.archived_at ? api.scanRuns.restore(scanRun.id) : api.scanRuns.archive(scanRun.id)).then(onChanged)}>
          {scanRun.archived_at ? <RotateCcw className="h-4 w-4" aria-hidden /> : <Archive className="h-4 w-4" aria-hidden />}
          {scanRun.archived_at ? "Restore" : "Archive"}
        </button>,
      ])}
    />
  );
}

function ScanRunDetail({ scanRun, summary, onOpen }: { scanRun: ScanRun | null; summary: ScanRunSummary | null; onOpen: (id: number) => void }) {
  return (
    <Section title="Scan Detail">
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
              <MetricCard label="Published" value={summary.published_mappings} accent="emerald" />
              <MetricCard label="Manual review" value={summary.manual_review_mappings} accent="amber" />
            </div>
          ) : (
            <LoadingState label="Loading summary" />
          )}
          <div className="pt-2">
            <button className="primary-button w-full justify-center" onClick={() => onOpen(scanRun.id)}>
              Open scan workspace
              <ArrowRight className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      ) : (
        <EmptyState label="Select a scan run to see details." />
      )}
    </Section>
  );
}
