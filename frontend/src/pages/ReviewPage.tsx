import { useMemo, useState } from "react";
import { Check, X } from "lucide-react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { BulkReviewDecision, ReviewQueueItem } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, Section, StatusBadge } from "../components/Primitives";
import { formatDate } from "../utils/format";

export function ReviewPage() {
  const [comment, setComment] = useState("Reviewed from frontend.");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [controlIdFilter, setControlIdFilter] = useState("");
  const [scanRunIdFilter, setScanRunIdFilter] = useState("");

  const reviewQueue = useResource(() =>
    api.reviewQueue.list({
      status: statusFilter || undefined,
      severity: severityFilter || undefined,
      control_id: controlIdFilter || undefined,
      scan_run_id: scanRunIdFilter ? Number(scanRunIdFilter) : undefined,
    }),
  );

  const someSelected = selectedIds.size > 0;
  const hasPending = (reviewQueue.data?.some((item) => item.status === "pending") ?? false);
  const pendingIds = reviewQueue.data?.filter((item) => item.status === "pending").map((item) => item.id) ?? [];
  const allPendingSelected = pendingIds.length > 0 && pendingIds.every((id) => selectedIds.has(id));

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allPendingSelected) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(pendingIds));
  }

  async function bulkDecide(action: "approve" | "reject", explicitIds?: number[]) {
    const itemIds = explicitIds ?? Array.from(selectedIds);
    const payload: BulkReviewDecision = {
      item_ids: itemIds,
      reviewer_id: "frontend-operator",
      comments: comment || undefined,
      action,
    };
    await api.reviewQueue.bulkDecide(payload);
    setSelectedIds(new Set());
    await reviewQueue.reload();
  }

  async function decide(id: number, action: "approve" | "reject") {
    if (action === "approve") {
      await api.reviewQueue.approve(id, comment);
    } else {
      await api.reviewQueue.reject(id, comment);
    }
    await reviewQueue.reload();
  }

  const filteredData = useMemo(() => {
    if (!reviewQueue.data) return [];
    return reviewQueue.data;
  }, [reviewQueue.data]);

  return (
    <Section
      title="Review Queue"
      description="Low-confidence or uncertain mappings require explicit human review."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <input className="control w-36" placeholder="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} />
          <input className="control w-28" placeholder="Severity" value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} />
          <input className="control w-28" placeholder="Control ID" value={controlIdFilter} onChange={(e) => setControlIdFilter(e.target.value)} />
          <input className="control w-24" placeholder="Scan run" value={scanRunIdFilter} onChange={(e) => setScanRunIdFilter(e.target.value)} type="number" />
        </div>
      }
    >
      <div className={`mb-4 flex flex-wrap items-center gap-2 transition-all duration-300 ${someSelected ? "translate-y-0 opacity-100" : "-translate-y-2 opacity-0 pointer-events-none"}`}>
        <input className="control w-72" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Review comment..." />
        <div className="flex gap-2">
          <button className="icon-button" disabled={!someSelected} onClick={() => bulkDecide("approve")}>
            <Check className="h-4 w-4" aria-hidden />
            Approve Selected ({selectedIds.size})
          </button>
          <button className="icon-button" disabled={!someSelected} onClick={() => bulkDecide("reject")}>
            <X className="h-4 w-4" aria-hidden />
            Reject Selected ({selectedIds.size})
          </button>
          <button className="icon-button" disabled={!hasPending} onClick={() => {
            const pendingIds = filteredData.filter(i => i.status === "pending").map(i => i.id);
            bulkDecide("approve", pendingIds);
          }}>
            Approve All Pending
          </button>
          <button className="icon-button" onClick={() => setSelectedIds(new Set())} disabled={!someSelected}>
            Clear Selection
          </button>
        </div>
      </div>
      <ResourceBoundary resource={reviewQueue}>
        {(data) => <ReviewTable data={data} selectedIds={selectedIds} onToggleSelect={toggleSelect} onToggleSelectAll={toggleSelectAll} allPendingSelected={allPendingSelected as boolean} onDecision={decide} />}
      </ResourceBoundary>
    </Section>
  );
}

function ReviewTable({
  data,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  allPendingSelected,
  onDecision,
}: {
  data: ReviewQueueItem[];
  selectedIds: Set<number>;
  onToggleSelect: (id: number) => void;
  onToggleSelectAll: () => void;
  allPendingSelected: boolean;
  onDecision: (id: number, action: "approve" | "reject") => void;
}) {
  return (
    <DataTable
      columns={["", "ID", "Mapping", "Status", "Reason", "Reviewed", "Decision"]}
      rows={data.map((item) => [
        <input
          key={`cb-${item.id}`}
          type="checkbox"
          checked={selectedIds.has(item.id)}
          onChange={() => onToggleSelect(item.id)}
          disabled={item.status !== "pending"}
          className="h-4 w-4 rounded border-line-strong text-brand-600 focus:ring-brand-500"
        />,
        item.id,
        item.control_mapping_id,
        <StatusBadge key={`status-${item.id}`} value={item.status} />,
        item.review_reason_code,
        formatDate(item.reviewed_at),
        <div key={`actions-${item.id}`} className="flex gap-2">
          <button className="icon-button !h-8 !px-3 !text-xs" disabled={item.status !== "pending"} onClick={() => onDecision(item.id, "approve")}>
            <Check className="h-3.5 w-3.5" aria-hidden />
            Approve
          </button>
          <button className="icon-button !h-8 !px-3 !text-xs" disabled={item.status !== "pending"} onClick={() => onDecision(item.id, "reject")}>
            <X className="h-3.5 w-3.5" aria-hidden />
            Reject
          </button>
        </div>,
      ])}
    />
  );
}
