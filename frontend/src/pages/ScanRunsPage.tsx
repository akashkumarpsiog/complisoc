import { useState } from "react";
import { Archive, ArrowRight, CheckCircle2, Play, RotateCcw } from "lucide-react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { ScanRun } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, Section, StatusBadge } from "../components/Primitives";
import { formatDate } from "../utils/format";
import { ScanRunCreator } from "../components/ScanRunCreator";

export function ScanRunsPage({ onSelectScan }: { onSelectScan: (id: number) => void }) {
  const [showArchived, setShowArchived] = useState(false);
  const scanRuns = useResource(() => api.scanRuns.list(showArchived), [showArchived]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [createdScan, setCreatedScan] = useState<ScanRun | null>(null);
  const [scanCreatorOpen, setScanCreatorOpen] = useState(false);

  async function handleCreated(scanRun: ScanRun) {
    await scanRuns.reload();
    setCreatedScan(scanRun);
  }

  return (
    <div className="grid gap-5">
      <Section
        title="Scan Runs"
        description={showArchived ? "Archived scan history only. Restore a scan to return it to active views." : "Active scans only. Archived scans remain available for audit."}
        actions={
          <div className="flex items-center gap-2">
            <button className="secondary-button" onClick={() => setShowArchived((value) => !value)}>
              {showArchived ? "Show active" : "Show archived"}
            </button>
            <button className="primary-button" onClick={() => setScanCreatorOpen(true)}>
              <Play className="h-4 w-4" aria-hidden />
              New scan
            </button>
          </div>
        }
      >
        {createdScan && (
          <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-success/20 bg-success-light px-4 py-3 text-sm font-medium text-success-dark">
            <span className="inline-flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" aria-hidden />
              Scan #{createdScan.id} was created. Open it from the table below.
            </span>
            <button className="text-xs font-semibold underline" onClick={() => setCreatedScan(null)}>Dismiss</button>
          </div>
        )}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button className="secondary-button" disabled={selectedIds.size === 0} onClick={() => { void api.scanRuns.bulkArchive(Array.from(selectedIds)).then(() => { setSelectedIds(new Set()); void scanRuns.reload(); }).catch(() => { alert("Archive failed. Please try again."); }); }}>
            Archive Selected ({selectedIds.size})
          </button>
          <button className="secondary-button" onClick={() => setSelectedIds(new Set())} disabled={selectedIds.size === 0}>
            Clear Selection
          </button>
        </div>
        <ResourceBoundary resource={scanRuns}>
          {(data) => <ScanRunTable data={data} onOpen={onSelectScan} onChanged={scanRuns.reload} selectedIds={selectedIds} onToggleSelect={(id) => setSelectedIds((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; })} />}
        </ResourceBoundary>
      </Section>
      <ScanRunCreator open={scanCreatorOpen} onOpenChange={setScanCreatorOpen} onCreated={handleCreated} />
    </div>
  );
}

function ScanRunTable({ data, onOpen, onChanged, selectedIds, onToggleSelect }: { data: ScanRun[]; onOpen: (id: number) => void; onChanged: () => Promise<void>; selectedIds: Set<number>; onToggleSelect: (id: number) => void }) {
  return (
    <DataTable
      columns={["", "ID", "Environment", "Status", "Created", "Open", "Retention"]}
      rows={data.map((scanRun) => [
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
