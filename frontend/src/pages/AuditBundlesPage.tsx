import { useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { AuditBundle, ScanRun } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, Section, StatusBadge } from "../components/Primitives";
import { formatDate } from "../utils/format";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

export function AuditBundlesPage() {
  const bundles = useResource(api.auditBundles.list);
  const scanRuns = useResource(api.scanRuns.list);
  const [scanRunId, setScanRunId] = useState("");
  const [verificationStatuses, setVerificationStatuses] = useState<Record<number, { status: string; loading: boolean; error?: string }>>({});

  async function create() {
    if (!scanRunId) return;
    await api.auditBundles.create(Number(scanRunId));
    await bundles.reload();
  }

  async function verifyBundle(bundleId: number) {
    setVerificationStatuses((prev) => ({ ...prev, [bundleId]: { status: "loading", loading: true } }));
    try {
      const result = await api.auditBundles.verify(bundleId);
      setVerificationStatuses((prev) => ({ ...prev, [bundleId]: { status: result.status, loading: false } }));
    } catch (err) {
      setVerificationStatuses((prev) => ({ ...prev, [bundleId]: { status: "error", loading: false, error: err instanceof Error ? err.message : "Verification failed" } }));
    }
  }

  return (
    <Section
      title="Audit Bundles"
      description="Exportable audit evidence with full lineage and integrity verification"
      actions={<BundleActions scanRuns={scanRuns.data || []} scanRunId={scanRunId} setScanRunId={setScanRunId} onCreate={create} />}
    >
      <ResourceBoundary resource={bundles}>
        {(data) => <BundleTable data={data} verificationStatuses={verificationStatuses} onVerify={verifyBundle} />}
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

function BundleTable({ data, verificationStatuses, onVerify }: { data: AuditBundle[]; verificationStatuses: Record<number, { status: string; loading: boolean; error?: string }>; onVerify: (id: number) => void }) {
  return (
    <DataTable
      columns={["ID", "Scan Run", "Generated", "Checksum", "Manifest", "Integrity", "Actions"]}
      rows={data.map((bundle) => {
        const verifyState = verificationStatuses[bundle.id];
        const statusBadge = verifyState ? (
          verifyState.loading ? (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Verifying...
            </span>
          ) : verifyState.status === "VALID" ? (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-success-dark">
              <CheckCircle2 className="h-3.5 w-3.5" /> Valid
            </span>
          ) : verifyState.status === "TAMPERED" ? (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-danger-dark">
              <XCircle className="h-3.5 w-3.5" /> Tampered
            </span>
          ) : (
            <span className="text-xs font-medium text-muted">{verifyState.status}</span>
          )
        ) : (
          <span className="text-xs text-muted">Not verified</span>
        );

        return [
          bundle.id,
          bundle.scan_run_id,
          formatDate(bundle.generated_at),
          <span key={`checksum-${bundle.id}`} className="font-mono text-xs" title={bundle.checksum}>{bundle.checksum.slice(0, 16)}…</span>,
          bundle.manifest_path ? <span key={`manifest-${bundle.id}`} className="text-xs text-success-dark font-medium">Present</span> : <span key={`manifest-${bundle.id}`} className="text-xs text-muted">None</span>,
          statusBadge,
          <div key={`actions-${bundle.id}`} className="flex items-center gap-2">
            <button className="secondary-button" onClick={() => onVerify(bundle.id)} disabled={verifyState?.loading}>
              Verify
            </button>
            <a className="icon-button" href={api.auditBundles.downloadUrl(bundle.id)}>
              Download
            </a>
          </div>,
        ];
      })}
    />
  );
}
