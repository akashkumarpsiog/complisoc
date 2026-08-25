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
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!selected) {
      setSummary(null);
      return;
    }
    void api.scanRuns.summary(selected.id).then(setSummary);
  }, [selected]);

  return (
    <div className="grid gap-5 2xl:grid-cols-[1fr_420px]">
      <Section
        title="Scan Runs"
        description={showArchived ? "Archived scan history only. Restore a scan to return it to active views." : "Active scans only. Archived scans remain available for audit."}
        actions={
          <div className="flex items-center gap-2">
            <button className="secondary-button" onClick={() => setShowArchived((value) => !value)}>
              {showArchived ? "Show active" : "Show archived"}
            </button>
            <ScanRunCreator onCreated={scanRuns.reload} />
          </div>
        }
      >
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button className="secondary-button" disabled={selectedIds.size === 0} onClick={() => { void api.scanRuns.bulkArchive(Array.from(selectedIds)).then(() => { setSelectedIds(new Set()); void scanRuns.reload(); }); }}>
            Archive Selected ({selectedIds.size})
          </button>
          <button className="secondary-button" onClick={() => setSelectedIds(new Set())} disabled={selectedIds.size === 0}>
            Clear Selection
          </button>
        </div>
        <ResourceBoundary resource={scanRuns}>
          {(data) => <ScanRunTable data={data} onSelect={setSelectedId} onOpen={onSelectScan} onChanged={scanRuns.reload} selectedIds={selectedIds} onToggleSelect={(id) => setSelectedIds((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; })} />}
        </ResourceBoundary>
      </Section>
      <ScanRunDetail scanRun={selected} summary={summary} onOpen={onSelectScan} />
    </div>
  );
}

function ScanRunTable({ data, onSelect, onOpen, onChanged, selectedIds, onToggleSelect }: { data: ScanRun[]; onSelect: (id: number) => void; onOpen: (id: number) => void; onChanged: () => Promise<void>; selectedIds: Set<number>; onToggleSelect: (id: number) => void }) {
  return (
    <DataTable
      columns={["", "ID", "Environment", "Status", "Created", "Open", "Retention"]}
      rows={data.map((scanRun, index) => [
        <input
          key={scanRun.id}
          type="checkbox"
          checked={selectedIds.has(scanRun.id)}
          onChange={() => onToggleSelect(scanRun.id)}
          className="h-4 w-4 rounded border-line-strong text-brand-600 focus:ring-brand-500"
        />,
        scanRun.id,
        scanRun.target_environment,
        <StatusBadge key={`status-${scanRun.id}`} value={scanRun.status} />,
        formatDate(scanRun.created_at),
        <button key={`open-${scanRun.id}`} className="primary-button !h-8 !px-3 !text-xs" onClick={() => onOpen(scanRun.id)}>
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          View
        </button>,
        <button key={`archive-${scanRun.id}`} className="secondary-button !h-8 !px-3 !text-xs" onClick={() => void (scanRun.archived_at ? api.scanRuns.restore(scanRun.id) : api.scanRuns.archive(scanRun.id)).then(onChanged)}>
          {scanRun.archived_at ? <RotateCcw className="h-3.5 w-3.5" aria-hidden /> : <Archive className="h-3.5 w-3.5" aria-hidden />}
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
        <div className="space-y-4 animate-slide-in-right">
          <Detail label="Scan run" value={scanRun.id} />
          <Detail label="Environment" value={scanRun.target_environment} />
          <Detail label="Status" value={<StatusBadge value={scanRun.status} />} />
          <Detail label="Started" value={formatDate(scanRun.started_at)} />
          {summary ? (
            <div className="grid grid-cols-2 gap-3 pt-3">
              <MetricCard label="Raw" value={summary.raw_findings} className="!p-4" />
              <MetricCard label="Normalized" value={summary.normalized_findings} className="!p-4" />
              <MetricCard label="Mappings" value={summary.mappings} className="!p-4" />
              <MetricCard label="Published" value={summary.published_mappings} accent="emerald" className="!p-4" />
              <MetricCard label="Manual review" value={summary.manual_review_mappings} accent="amber" className="!p-4" />
            </div>
          ) : (
            <LoadingState label="Loading summary" />
          )}
          <div className="pt-3">
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
