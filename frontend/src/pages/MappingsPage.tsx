import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { ControlMapping, VerificationRecord } from "../types";
import { Detail } from "../components/Detail";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, EmptyState, LoadingState, Section, StatusBadge } from "../components/Primitives";
import { formatPercent } from "../utils/format";

const statuses = ["published", "manual_review", "rejected", "validated", "verified"];

export function MappingsPage() {
  const mappings = useResource(api.mappings.list);
  const [status, setStatus] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = mappings.data?.find((item) => item.id === selectedId) || null;
  const filtered = useMemo(() => (mappings.data || []).filter((item) => !status || item.mapping_status === status), [mappings.data, status]);

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <Section title="Mappings" actions={<MappingStatusFilter value={status} onChange={setStatus} />}>
        <ResourceBoundary resource={{ ...mappings, data: filtered }}>
          {(data) => <MappingTable data={data} onSelect={setSelectedId} />}
        </ResourceBoundary>
      </Section>
      <MappingDetail mapping={selected} />
    </div>
  );
}

function MappingStatusFilter({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <select className="control" value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">All statuses</option>
      {statuses.map((item) => (
        <option key={item}>{item}</option>
      ))}
    </select>
  );
}

function MappingTable({ data, onSelect }: { data: ControlMapping[]; onSelect: (id: number) => void }) {
  return (
    <DataTable
      columns={["ID", "Finding", "Control", "Status", "Confidence", "Open"]}
      rows={data.map((mapping) => [
        mapping.id,
        mapping.normalized_finding_id,
        mapping.control_catalog_id,
        <StatusBadge value={mapping.mapping_status} />,
        formatPercent(mapping.final_confidence),
        <button className="icon-button" onClick={() => onSelect(mapping.id)}>
          Detail
        </button>,
      ])}
    />
  );
}

function MappingDetail({ mapping }: { mapping: ControlMapping | null }) {
  const [verification, setVerification] = useState<VerificationRecord[] | null>(null);

  useEffect(() => {
    if (!mapping) {
      setVerification(null);
      return;
    }
    void api.mappings.verification(mapping.id).then(setVerification);
  }, [mapping]);

  return (
    <Section title="Mapping Detail">
      {mapping ? (
        <div className="space-y-3">
          <Detail label="Mapping" value={mapping.id} />
          <Detail label="Finding" value={mapping.normalized_finding_id} />
          <Detail label="Control" value={mapping.control_catalog_id} />
          <Detail label="Gemini" value={formatPercent(mapping.gemini_confidence)} />
          <Detail label="Final" value={formatPercent(mapping.final_confidence)} />
          <Detail label="Status" value={<StatusBadge value={mapping.mapping_status} />} />
          <Detail label="Rationale" value={mapping.rationale || "n/a"} />
          <h3 className="pt-2 text-sm font-semibold">Verification</h3>
          {verification ? <VerificationTable data={verification} /> : <LoadingState label="Loading verification" />}
        </div>
      ) : (
        <EmptyState label="Select a mapping." />
      )}
    </Section>
  );
}

function VerificationTable({ data }: { data: VerificationRecord[] }) {
  return (
    <DataTable
      columns={["ID", "Result", "Model", "Explanation"]}
      rows={data.map((record) => [record.id, <StatusBadge value={record.result} />, record.verification_model, record.explanation || "n/a"])}
    />
  );
}
