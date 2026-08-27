import { useEffect, useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { AuditBundle, ScanRun } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, Section, StatusBadge } from "../components/Primitives";
import { formatDate } from "../utils/format";
import { CheckCircle2, XCircle, ShieldCheck, ShieldAlert, Info } from "lucide-react";

interface VerificationResult {
  bundle_id: number;
  status: string;
  bundle_verified: boolean;
  manifest_verified: boolean;
  files: Record<string, string>;
  errors: string[];
}

export function AuditBundlesPage() {
  const bundles = useResource(api.auditBundles.list);
  const scanRuns = useResource(api.scanRuns.list);
  const [scanRunId, setScanRunId] = useState("");
  const [verificationResults, setVerificationResults] = useState<Record<number, VerificationResult>>({});
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    if (bundles.data && bundles.data.length > 0 && Object.keys(verificationResults).length === 0 && !verifying) {
      void runVerification();
    }
  }, [bundles.data]);

  async function runVerification() {
    setVerifying(true);
    try {
      const results = await api.auditBundles.verifyAll();
      const mapped: Record<number, VerificationResult> = {};
      const bundleList = bundles.data || [];
      for (let i = 0; i < results.length && i < bundleList.length; i++) {
        mapped[bundleList[i].id] = { ...results[i], bundle_id: bundleList[i].id };
      }
      setVerificationResults(mapped);
    } catch {
      setVerificationResults({});
    } finally {
      setVerifying(false);
    }
  }

  async function create() {
    if (!scanRunId) return;
    await api.auditBundles.create(Number(scanRunId));
    await bundles.reload();
  }

  return (
    <Section
      title="Audit Bundles"
      description="Exportable audit evidence with full lineage and integrity verification"
      actions={<BundleActions scanRuns={scanRuns.data || []} scanRunId={scanRunId} setScanRunId={setScanRunId} onCreate={create} />}
    >
      <div className="mb-5 rounded-xl border border-brand/20 bg-brand-light p-4">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-brand-600 mt-0.5 shrink-0" aria-hidden />
          <div className="text-sm text-brand-900">
            <p className="font-semibold mb-1">How integrity verification works</p>
            <p className="leading-relaxed text-brand-800">
              Each audit bundle is a JSON artifact containing the full compliance evidence for a scan run.
              When generated, a SHA-256 checksum is computed and stored. Verification re-computes the checksum
              of the stored file and compares it against the original. A <span className="font-semibold">Valid</span> result
              means the file is byte-identical to what was generated — it has not been modified, corrupted, or tampered with.
              This gives auditors and regulators confidence that the evidence is authentic.
            </p>
          </div>
        </div>
      </div>

      <ResourceBoundary resource={bundles}>
        {(data) => <BundleTable data={data} verificationResults={verificationResults} verifying={verifying} onRefreshVerification={runVerification} />}
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

function BundleTable({ data, verificationResults, verifying, onRefreshVerification }: { data: AuditBundle[]; verificationResults: Record<number, VerificationResult>; verifying: boolean; onRefreshVerification: () => void }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-subtle">
          {verifying ? "Verifying integrity..." : `${data.length} bundle${data.length === 1 ? "" : "s"} · auto-verified on load`}
        </p>
        <button className="secondary-button !py-1.5 !text-xs" onClick={onRefreshVerification} disabled={verifying}>
          {verifying ? "Verifying..." : "Re-verify all"}
        </button>
      </div>
      <DataTable
        columns={["ID", "Scan Run", "Generated", "Checksum", "Integrity", "Details", "Actions"]}
        rows={data.map((bundle) => {
          const result = verificationResults[bundle.id];
          return [
            bundle.id,
            bundle.scan_run_id,
            formatDate(bundle.generated_at),
            <span key={`checksum-${bundle.id}`} className="font-mono text-xs" title={bundle.checksum}>{bundle.checksum.slice(0, 16)}…</span>,
            <IntegrityStatus key={`integrity-${bundle.id}`} result={result} verifying={verifying} />,
            <VerificationDetails key={`details-${bundle.id}`} result={result} bundle={bundle} />,
            <div key={`actions-${bundle.id}`} className="flex items-center gap-2">
              <a className="icon-button" href={api.auditBundles.downloadUrl(bundle.id)}>
                Download
              </a>
            </div>,
          ];
        })}
      />
    </div>
  );
}

function IntegrityStatus({ result, verifying }: { result?: VerificationResult; verifying: boolean }) {
  if (verifying && !result) {
    return <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted">Checking...</span>;
  }
  if (!result) {
    return <span className="text-xs text-muted">Pending</span>;
  }
  if (result.status === "VALID") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-success-dark">
        <ShieldCheck className="h-3.5 w-3.5" /> Valid
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-danger-dark">
      <ShieldAlert className="h-3.5 w-3.5" /> Tampered
    </span>
  );
}

function VerificationDetails({ result, bundle }: { result?: VerificationResult; bundle: AuditBundle }) {
  if (!result) {
    return <span className="text-xs text-muted">—</span>;
  }

  return (
    <div className="space-y-1.5 text-xs">
      <div className="flex items-center gap-1.5">
        {result.bundle_verified ? (
          <CheckCircle2 className="h-3.5 w-3.5 text-success-dark" aria-hidden />
        ) : (
          <XCircle className="h-3.5 w-3.5 text-danger-dark" aria-hidden />
        )}
        <span className={result.bundle_verified ? "text-success-dark" : "text-danger-dark"}>
          Bundle {result.bundle_verified ? "checksum matches" : "checksum mismatch"}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        {result.manifest_verified ? (
          <CheckCircle2 className="h-3.5 w-3.5 text-success-dark" aria-hidden />
        ) : (
          <XCircle className="h-3.5 w-3.5 text-danger-dark" aria-hidden />
        )}
        <span className={result.manifest_verified ? "text-success-dark" : "text-danger-dark"}>
          Manifest {result.manifest_verified ? "present" : "missing"}
        </span>
      </div>
      {result.errors.length > 0 && (
        <div className="text-danger-dark">
          {result.errors.map((err, i) => (
            <div key={i}>{err}</div>
          ))}
        </div>
      )}
    </div>
  );
}
