import { useMemo, useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { ControlMapping } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, Section, StatusBadge } from "../components/Primitives";
import { formatPercent } from "../utils/format";

export function MappingsPage() {
  const mappings = useResource(api.mappings.list);
  const [status, setStatus] = useState("");
  const filtered = useMemo(() => (mappings.data || []).filter((item) => !status || item.mapping_status === status), [mappings.data, status]);
  const statusOptions = useMemo(() => Array.from(new Set((mappings.data || []).map((m) => m.mapping_status))).sort(), [mappings.data]);

  return (
    <Section title="Mappings" description="Control mappings generated from findings" actions={<MappingStatusFilter value={status} options={statusOptions} onChange={setStatus} />}>
      <ResourceBoundary resource={{ ...mappings, data: filtered }}>
        {(data) => <MappingTable data={data} />}
      </ResourceBoundary>
    </Section>
  );
}

function MappingStatusFilter({ value, options, onChange }: { value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <select className="control" value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">All statuses</option>
      {options.map((item) => (
        <option key={item}>{item}</option>
      ))}
    </select>
  );
}

function MappingTable({ data }: { data: ControlMapping[] }) {
  return (
    <DataTable
      columns={["ID", "Finding", "Control", "AI Verdict", "Gemini Score", "Groq Score", "Final Confidence", "Groq Verdict"]}
      rows={data.map((mapping) => [
        mapping.id,
        mapping.normalized_finding_id,
        mapping.control_catalog_id,
        <StatusBadge key={`vs-${mapping.id}`} value={mapping.mapping_status} />,
        formatPercent(mapping.gemini_confidence),
        formatPercent(mapping.groq_agreement_value),
        formatPercent(mapping.final_confidence),
        <StatusBadge key={`gv-${mapping.id}`} value={mapping.verification_status || "not verified"} />,
      ])}
    />
  );
}
