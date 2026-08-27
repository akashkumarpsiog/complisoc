import { useMemo, useState } from "react";
import { Check, X, Loader2, AlertCircle } from "lucide-react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { BulkReviewDecision, ReviewQueueItem } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, Section, StatusBadge } from "../components/Primitives";
import { formatDate } from "../utils/format";

type ActionStatus = Record<number, "approving" | "rejecting" | "idle">;

function uniqueValues(values: (string | null | undefined)[]): string[] {
  return Array.from(new Set(values.filter((v): v is string => Boolean(v)))).sort();
}

export function ReviewPage() {
  const [comment, setComment] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [severityFilter, setSeverityFilter] = useState("");
  const [controlIdFilter, setControlIdFilter] = useState("");
  const [scanRunIdFilter, setScanRunIdFilter] = useState("");
  const [actionStatuses, setActionStatuses] = useState<ActionStatus>({});
  const [bulkLoading, setBulkLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allReviewItems = useResource(() => api.reviewQueue.list({}), []);

  const reviewQueue = useResource(
    () =>
      api.reviewQueue.list({
        severity: severityFilter || undefined,
        control_id: controlIdFilter || undefined,
        scan_run_id: scanRunIdFilter ? Number(scanRunIdFilter) : undefined,
      }),
    [severityFilter, controlIdFilter, scanRunIdFilter],
  );

  const data = reviewQueue.data || [];

  const allItems = allReviewItems.data || [];
  const severityOptions = useMemo(() => uniqueValues(allItems.map((i) => i.severity)), [allItems]);
  const controlIdOptions = useMemo(() => uniqueValues(allItems.map((i) => i.control_id)), [allItems]);
  const scanRunOptions = useMemo(
    () =>
      Array.from(
        new Map(
          allItems
            .filter((i): i is ReviewQueueItem & { scan_run_id: number } => i.scan_run_id != null)
            .map((i) => [i.scan_run_id, i]),
        ).values(),
      ).sort((a, b) => b.scan_run_id - a.scan_run_id),
    [allItems],
  );

  const pendingItems = useMemo(() => data.filter((item) => item.status === "pending"), [data]);
  const pendingIds = useMemo(() => pendingItems.map((item) => item.id), [pendingItems]);
  const allPendingSelected =
    pendingIds.length > 0 && pendingIds.every((id) => selectedIds.has(id));
  const someSelected = selectedIds.size > 0;

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
    setSelectedIds(new Set(pendingItems.map((item) => item.id)));
  }

  function clearSelection() {
    setSelectedIds(new Set());
    setError(null);
  }

  async function decide(id: number, action: "approve" | "reject") {
    setActionStatuses((prev) => ({ ...prev, [id]: action === "approve" ? "approving" : "rejecting" }));
    setError(null);
    try {
      if (action === "approve") {
        await api.reviewQueue.approve(id, comment);
      } else {
        await api.reviewQueue.reject(id, comment);
      }
      await reviewQueue.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setActionStatuses((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
  }

  async function bulkDecide(action: "approve" | "reject", explicitIds?: number[]) {
    const itemIds = explicitIds ?? Array.from(selectedIds);
    if (itemIds.length === 0) return;
    setBulkLoading(true);
    setError(null);
    try {
      const payload: BulkReviewDecision = {
        item_ids: itemIds,
        reviewer_id: "frontend-operator",
        comments: comment || undefined,
        action,
      };
      await api.reviewQueue.bulkDecide(payload);
      setSelectedIds(new Set());
      await reviewQueue.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk action failed");
    } finally {
      setBulkLoading(false);
    }
  }

  return (
    <Section
      title="Review Queue"
      description="Low-confidence or uncertain mappings require explicit human review."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="control w-32"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
          >
            <option value="">All severities</option>
            {severityOptions.map((sev) => (
              <option key={sev} value={sev}>{sev}</option>
            ))}
          </select>
          <select
            className="control w-40"
            value={controlIdFilter}
            onChange={(e) => setControlIdFilter(e.target.value)}
          >
            <option value="">All controls</option>
            {controlIdOptions.map((cid) => (
              <option key={cid} value={cid}>{cid}</option>
            ))}
          </select>
          <select
            className="control w-48"
            value={scanRunIdFilter}
            onChange={(e) => setScanRunIdFilter(e.target.value)}
          >
            <option value="">All scan runs</option>
            {scanRunOptions.map((item) => (
              <option key={item.scan_run_id} value={item.scan_run_id}>
                Scan #{item.scan_run_id}
              </option>
            ))}
          </select>
        </div>
      }
    >
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-danger/20 bg-danger-light px-4 py-3 text-sm text-danger-dark">
          <AlertCircle className="h-4 w-4" aria-hidden />
          {error}
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          className="control w-72"
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Review comment..."
        />
        <div className="flex gap-2">
          <button
            className="icon-button"
            disabled={bulkLoading || pendingItems.length === 0}
            onClick={() => bulkDecide("approve", pendingItems.map((i) => i.id))}
          >
            {bulkLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Check className="h-4 w-4" aria-hidden />
            )}
            Approve All Pending
          </button>
        </div>
      </div>

      {someSelected && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="flex gap-2">
            <button
              className="icon-button"
              disabled={bulkLoading}
              onClick={() => bulkDecide("approve")}
            >
              {bulkLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <Check className="h-4 w-4" aria-hidden />
              )}
              Approve Selected ({selectedIds.size})
            </button>
            <button
              className="icon-button"
              disabled={bulkLoading}
              onClick={() => bulkDecide("reject")}
            >
              {bulkLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <X className="h-4 w-4" aria-hidden />
              )}
              Reject Selected ({selectedIds.size})
            </button>
            <button className="icon-button" onClick={clearSelection}>
              Clear Selection
            </button>
          </div>
        </div>
      )}

      <ResourceBoundary resource={reviewQueue}>
        {(items) => (
          <ReviewTable
            data={items}
            selectedIds={selectedIds}
            actionStatuses={actionStatuses}
            onToggleSelect={toggleSelect}
            onToggleSelectAll={toggleSelectAll}
            allPendingSelected={allPendingSelected}
            onDecision={decide}
          />
        )}
      </ResourceBoundary>
    </Section>
  );
}

function ReviewTable({
  data,
  selectedIds,
  actionStatuses,
  onToggleSelect,
  onToggleSelectAll,
  allPendingSelected,
  onDecision,
}: {
  data: ReviewQueueItem[];
  selectedIds: Set<number>;
  actionStatuses: ActionStatus;
  onToggleSelect: (id: number) => void;
  onToggleSelectAll: () => void;
  allPendingSelected: boolean;
  onDecision: (id: number, action: "approve" | "reject") => void;
}) {
  const pendingCount = data.filter((item) => item.status === "pending").length;

  return (
    <DataTable
      columns={[
        <label key="select-all" className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={allPendingSelected}
            onChange={onToggleSelectAll}
            disabled={pendingCount === 0}
            className="h-4 w-4 rounded border-line-strong text-brand-600 focus:ring-brand-500"
          />
          <span className="text-xs font-semibold uppercase tracking-wider text-subtle">All</span>
        </label>,
        "ID",
        "Mapping",
        "Severity",
        "Control ID",
        "Scan Run",
        "Status",
        "Reason",
        "Reviewed",
        "Decision",
      ]}
      rows={data.map((item) => {
        const isPending = item.status === "pending";
        const status = actionStatuses[item.id];
        const busy = status === "approving" || status === "rejecting";

        return [
          <input
            key={`cb-${item.id}`}
            type="checkbox"
            checked={selectedIds.has(item.id)}
            onChange={() => onToggleSelect(item.id)}
            disabled={!isPending || busy}
            className="h-4 w-4 rounded border-line-strong text-brand-600 focus:ring-brand-500"
          />,
          item.id,
          item.control_mapping_id,
          <span key={`sev-${item.id}`} className="capitalize">{item.severity ?? "—"}</span>,
          item.control_id ?? "—",
          item.scan_run_id != null ? `#${item.scan_run_id}` : "—",
          <StatusBadge key={`status-${item.id}`} value={item.status} />,
          item.review_reason_code,
          formatDate(item.reviewed_at),
          <div key={`actions-${item.id}`} className="flex items-center gap-2">
            <button
              className="icon-button !h-8 !px-3 !text-xs"
              disabled={!isPending || busy}
              onClick={() => onDecision(item.id, "approve")}
            >
              {busy && status === "approving" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <Check className="h-3.5 w-3.5" aria-hidden />
              )}
              {busy && status === "approving" ? "Approving..." : "Approve"}
            </button>
            <button
              className="icon-button !h-8 !px-3 !text-xs"
              disabled={!isPending || busy}
              onClick={() => onDecision(item.id, "reject")}
            >
              {busy && status === "rejecting" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <X className="h-3.5 w-3.5" aria-hidden />
              )}
              {busy && status === "rejecting" ? "Rejecting..." : "Reject"}
            </button>
          </div>,
        ];
      })}
    />
  );
}
