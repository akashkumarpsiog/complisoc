import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { ControlMapping, NormalizedFinding } from "../types";
import { Detail } from "../components/Detail";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, EmptyState, LoadingState, Section, StatusBadge } from "../components/Primitives";
import { formatPercent, includesText, severityOrder } from "../utils/format";

export function FindingsPage() {
  const findings = useResource(api.findings.list);
  const [severity, setSeverity] = useState("");
  const [scanner, setScanner] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = findings.data?.find((item) => item.id === selectedId) || null;
  const filtered = useMemo(
    () => (findings.data || []).filter((item) => (!severity || item.severity === severity) && (!scanner || includesText(item.scanner_name, scanner))),
    [findings.data, severity, scanner],
  );

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <Section title="Findings" actions={<FindingFilters severity={severity} scanner={scanner} setSeverity={setSeverity} setScanner={setScanner} />}>
        <ResourceBoundary resource={{ ...findings, data: filtered }}>
          {(data) => <FindingTable data={data} onSelect={setSelectedId} />}
        </ResourceBoundary>
      </Section>
      <FindingDetail finding={selected} />
    </div>
  );
}

function FindingFilters(props: {
  severity: string;
  scanner: string;
  setSeverity: (value: string) => void;
  setScanner: (value: string) => void;
}) {
  return (
    <>
      <select className="control" value={props.severity} onChange={(event) => props.setSeverity(event.target.value)}>
        <option value="">All severities</option>
        {severityOrder.map((item) => (
          <option key={item}>{item}</option>
        ))}
      </select>
      <input className="control" placeholder="Scanner" value={props.scanner} onChange={(event) => props.setScanner(event.target.value)} />
    </>
  );
}

function FindingTable({ data, onSelect }: { data: NormalizedFinding[]; onSelect: (id: number) => void }) {
  return (
    <DataTable
      columns={["ID", "Severity", "Scanner", "Resource", "Title", "Open"]}
      rows={data.map((finding) => [
        finding.id,
        <StatusBadge value={finding.severity} />,
        finding.scanner_name,
        finding.resource_identifier,
        finding.title,
        <button className="icon-button" onClick={() => onSelect(finding.id)}>
          Detail
        </button>,
      ])}
    />
  );
}

function FindingDetail({ finding }: { finding: NormalizedFinding | null }) {
  const [mappings, setMappings] = useState<ControlMapping[] | null>(null);

  useEffect(() => {
    if (!finding) {
      setMappings(null);
      return;
    }
    void api.findings.mappings(finding.id).then(setMappings);
  }, [finding]);

  return (
    <Section title="Finding Detail">
      {finding ? (
        <div className="space-y-3">
          <Detail label="Normalized" value={finding.id} />
          <Detail label="Raw finding" value={finding.raw_finding_id} />
          <Detail label="Severity" value={<StatusBadge value={finding.severity} />} />
          <Detail label="Type" value={finding.finding_type} />
          <Detail label="Resource" value={finding.resource_identifier} />
          <Detail label="Description" value={finding.description || "n/a"} />
          <h3 className="pt-2 text-sm font-semibold">Mappings</h3>
          {mappings ? (
            <DataTable
              columns={["Mapping", "Control", "Status", "Confidence"]}
              rows={mappings.map((mapping) => [
                mapping.id,
                mapping.control_catalog_id,
                <StatusBadge value={mapping.mapping_status} />,
                formatPercent(mapping.final_confidence),
              ])}
            />
          ) : (
            <LoadingState label="Loading mappings" />
          )}
        </div>
      ) : (
        <EmptyState label="Select a finding." />
      )}
    </Section>
  );
}
