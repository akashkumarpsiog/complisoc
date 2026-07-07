import { useMemo, useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { Control } from "../types";
import { Detail } from "../components/Detail";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, EmptyState, Section } from "../components/Primitives";

export function ControlsPage() {
  const controls = useResource(api.controls.list);
  const [framework, setFramework] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = controls.data?.find((item) => item.id === selectedId) || null;
  const frameworks = Array.from(new Set((controls.data || []).map((item) => item.framework_name))).sort();
  const filtered = useMemo(() => (controls.data || []).filter((item) => !framework || item.framework_name === framework), [controls.data, framework]);

  return (
    <div className="grid gap-5 2xl:grid-cols-[1fr_420px]">
      <Section title="Controls" actions={<FrameworkFilter frameworks={frameworks} value={framework} onChange={setFramework} />}>
        <ResourceBoundary resource={{ ...controls, data: filtered }}>
          {(data) => <ControlTable data={data} onSelect={setSelectedId} />}
        </ResourceBoundary>
      </Section>
      <ControlDetail control={selected} />
    </div>
  );
}

function FrameworkFilter({ frameworks, value, onChange }: { frameworks: string[]; value: string; onChange: (value: string) => void }) {
  return (
    <select className="control" value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">All frameworks</option>
      {frameworks.map((item) => (
        <option key={item}>{item}</option>
      ))}
    </select>
  );
}

function ControlTable({ data, onSelect }: { data: Control[]; onSelect: (id: number) => void }) {
  return (
    <DataTable
      columns={["ID", "Framework", "Control", "Family", "Title", "Open"]}
      rows={data.map((control) => [
        control.id,
        control.framework_name,
        control.control_id,
        control.control_family,
        control.title,
        <button className="icon-button" onClick={() => onSelect(control.id)}>
          Detail
        </button>,
      ])}
    />
  );
}

function ControlDetail({ control }: { control: Control | null }) {
  return (
    <Section title="Control Detail">
      {control ? (
        <div className="space-y-3">
          <Detail label="Framework" value={control.framework_name} />
          <Detail label="Version" value={control.framework_version} />
          <Detail label="Control" value={control.control_id} />
          <Detail label="Family" value={control.control_family} />
          <Detail label="Title" value={control.title} />
          <Detail label="Objective" value={control.objective || "n/a"} />
          <Detail label="Keywords" value={(control.keywords || []).join(", ") || "n/a"} />
        </div>
      ) : (
        <EmptyState label="Select a control." />
      )}
    </Section>
  );
}
