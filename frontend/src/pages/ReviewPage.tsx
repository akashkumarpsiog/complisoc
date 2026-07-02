import { useState } from "react";
import { Check, X } from "lucide-react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { ReviewQueueItem } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, Section, StatusBadge } from "../components/Primitives";
import { formatDate } from "../utils/format";

export function ReviewPage() {
  const reviewQueue = useResource(api.reviewQueue.list);
  const [comment, setComment] = useState("Reviewed from frontend.");

  async function decide(id: number, action: "approve" | "reject") {
    if (action === "approve") {
      await api.reviewQueue.approve(id, comment);
    } else {
      await api.reviewQueue.reject(id, comment);
    }
    await reviewQueue.reload();
  }

  return (
    <Section
      title="Review Queue"
      description="Low-confidence or uncertain mappings require explicit human review."
      actions={<input className="control w-72" value={comment} onChange={(event) => setComment(event.target.value)} />}
    >
      <ResourceBoundary resource={reviewQueue}>
        {(data) => <ReviewTable data={data} onDecision={decide} />}
      </ResourceBoundary>
    </Section>
  );
}

function ReviewTable({ data, onDecision }: { data: ReviewQueueItem[]; onDecision: (id: number, action: "approve" | "reject") => void }) {
  return (
    <DataTable
      columns={["ID", "Mapping", "Status", "Reason", "Reviewed", "Decision"]}
      rows={data.map((item) => [
        item.id,
        item.control_mapping_id,
        <StatusBadge value={item.status} />,
        item.review_reason_code,
        formatDate(item.reviewed_at),
        <div className="flex gap-2">
          <button className="icon-button" disabled={item.status !== "pending"} onClick={() => onDecision(item.id, "approve")}>
            <Check className="h-4 w-4" aria-hidden />
            Approve
          </button>
          <button className="icon-button" disabled={item.status !== "pending"} onClick={() => onDecision(item.id, "reject")}>
            <X className="h-4 w-4" aria-hidden />
            Reject
          </button>
        </div>,
      ])}
    />
  );
}
