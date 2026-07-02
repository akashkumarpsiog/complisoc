import { useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { AuditBundle, ScanRun } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, Section } from "../components/Primitives";
import { formatDate } from "../utils/format";

export function AuditBundlesPage() {
  const bundles = useResource(api.auditBundles.list);
  const scanRuns = useResource(api.scanRuns.list);
  const [scanRunId, setScanRunId] = useState("");

  async function create() {
    if (!scanRunId) return;
    await api.auditBundles.create(Number(scanRunId));
    await bundles.reload();
  }

  return (
    <Section
      title="Audit Bundles"
      actions={<BundleActions scanRuns={scanRuns.data || []} scanRunId={scanRunId} setScanRunId={setScanRunId} onCreate={create} />}
    >
      <ResourceBoundary resource={bundles}>
        {(data) => <BundleTable data={data} />}
      </ResourceBoundary>
    </Section>
  );
}

function BundleActions({
  scanRuns,
  scanRunId,
  setScanRunId,
  onCreate,
}: {
  scanRuns: ScanRun[];
  scanRunId: string;
  setScanRunId: (value: string) => void;
  onCreate: () => void;
}) {
  return (
    <>
      <select className="control" value={scanRunId} onChange={(event) => setScanRunId(event.target.value)}>
        <option value="">Scan run</option>
        {scanRuns.map((scanRun) => (
          <option key={scanRun.id} value={scanRun.id}>
            {scanRun.id} {scanRun.target_environment}
          </option>
        ))}
      </select>
      <button className="icon-button" disabled={!scanRunId} onClick={onCreate}>
        Generate
      </button>
    </>
  );
}

function BundleTable({ data }: { data: AuditBundle[] }) {
  return (
    <DataTable
      columns={["ID", "Scan Run", "Generated", "Checksum", "Download"]}
      rows={data.map((bundle) => [
        bundle.id,
        bundle.scan_run_id,
        formatDate(bundle.generated_at),
        bundle.checksum,
        <a className="icon-button" href={api.auditBundles.downloadUrl(bundle.id)}>
          Download
        </a>,
      ])}
    />
  );
}
