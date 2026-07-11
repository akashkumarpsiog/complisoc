import { useEffect, useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Cloud, Folder, GitBranch, Loader2, Play, Terminal, X } from "lucide-react";
import { api } from "../services/api";
import type { ScannerInfo } from "../types";
import { sampleFailures, sampleFindings } from "../services/json";

type Mode = "live" | "sample";
type TargetType = "local" | "git" | "aws" | "azure";

const TARGET_OPTIONS: { value: TargetType; label: string; icon: ReactNode }[] = [
  { value: "local", label: "Local Folder", icon: <Folder className="h-4 w-4" aria-hidden /> },
  { value: "git", label: "Git Repository", icon: <GitBranch className="h-4 w-4" aria-hidden /> },
  { value: "aws", label: "AWS Account", icon: <Cloud className="h-4 w-4" aria-hidden /> },
  { value: "azure", label: "Azure Subscription", icon: <Cloud className="h-4 w-4" aria-hidden /> },
];

export function ScanRunCreator({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("live");
  const [busy, setBusy] = useState(false);

  if (!open) {
    return (
      <button className="primary-button" onClick={() => setOpen(true)}>
        <Play className="h-4 w-4" aria-hidden />
        New scan
      </button>
    );
  }

  function close() {
    if (!busy) setOpen(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={close} />
      <div className="relative max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl border border-line bg-white shadow-xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-white px-4 py-3">
          <div className="flex gap-2">
            <button
              disabled={busy}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                mode === "live" ? "bg-brand-600 text-white" : "bg-panel text-slate-600 hover:bg-slate-100"
              }`}
              onClick={() => setMode("live")}
            >
              Live scan
            </button>
            <button
              disabled={busy}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                mode === "sample" ? "bg-brand-600 text-white" : "bg-panel text-slate-600 hover:bg-slate-100"
              }`}
              onClick={() => setMode("sample")}
            >
              Sample scan
            </button>
          </div>
          <button className="icon-button border-0 p-1" disabled={busy} onClick={close} aria-label="Close">
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <div className="p-4">
          {mode === "live" ? (
            <LiveScanForm onBusyChange={setBusy} onCreated={onCreated} onClose={close} />
          ) : (
            <SampleScanForm onBusyChange={setBusy} onCreated={onCreated} onClose={close} />
          )}
        </div>
      </div>
    </div>
  );
}

function LiveScanForm({
  onBusyChange,
  onCreated,
  onClose,
}: {
  onBusyChange: (busy: boolean) => void;
  onCreated: () => void;
  onClose: () => void;
}) {
  const [scanners, setScanners] = useState<ScannerInfo[]>([]);
  const [targetType, setTargetType] = useState<TargetType>("local");
  const [target, setTarget] = useState(".");
  const [framework, setFramework] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showProviders, setShowProviders] = useState(false);

  useEffect(() => {
    void api.scanners.list().then(setScanners);
  }, []);

  useEffect(() => {
    onBusyChange(submitting);
  }, [onBusyChange, submitting]);

  useEffect(() => {
    if (targetType === "local") setTarget(".");
    if (targetType === "aws") setTarget("aws-iac-container");
    if (targetType === "azure") setTarget("azure-subscription");
    if (targetType === "git") setTarget("");
  }, [targetType]);

  const scannerMap = Object.fromEntries(scanners.map((s) => [s.name, s]));
  const availableCount = scanners.filter((s) => s.available).length;

  const infrastructure = scannerMap.checkov;
  const vulnerability = scannerMap.trivy;
  const staticAnalysis = scannerMap.sonarqube;
  const cloudFindings = scannerMap.defender;

  const isStaticConfigured = staticAnalysis?.available ?? false;
  const isInfraAvailable = infrastructure?.available ?? false;
  const isVulnAvailable = vulnerability?.available ?? false;

  async function submit() {
    if (submitting) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const result = await api.scans.run({
        target,
        scan_profile: targetType,
        framework: framework.trim() || undefined,
      });
      setMessage(`Created scan run ${result.id} from live scan.`);
      onCreated();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to run scan.");
    } finally {
      setSubmitting(false);
    }
  }

  const targetLabel =
    targetType === "azure"
      ? "Azure subscription or resource scope"
      : targetType === "aws"
        ? "AWS IaC/container target"
        : targetType === "git"
          ? "Repository URL or local path"
          : "Target path";
  const targetPlaceholder =
    targetType === "azure"
      ? "azure-subscription or resource group label"
      : targetType === "aws"
        ? "terraform dir, docker image, or project label"
        : targetType === "git"
          ? "owner/repo or C:/path/to/repo"
          : ". or C:/repo";

  return (
    <div className="grid gap-4">
      <div>
        <div className="mb-2 text-sm font-medium">Target</div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {TARGET_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={submitting}
              onClick={() => setTargetType(option.value)}
              className={`inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition ${
                targetType === option.value
                  ? "border-brand-200 bg-brand-50 text-brand-700"
                  : "border-line bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {option.icon}
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <label className="text-sm font-medium">
        {targetLabel}
        <input className="control mt-1" disabled={submitting} value={target} onChange={(event) => setTarget(event.target.value)} placeholder={targetPlaceholder} />
      </label>

      <div className="rounded-md border border-line bg-panel p-3">
        <button
          type="button"
          onClick={() => setShowProviders((prev) => !prev)}
          className="flex w-full items-center justify-between text-sm font-medium text-slate-700"
        >
          <span>Security providers used in this scan</span>
          {showProviders ? <ChevronDown className="h-4 w-4 text-slate-400" aria-hidden /> : <ChevronRight className="h-4 w-4 text-slate-400" aria-hidden />}
        </button>
        {showProviders ? (
          <div className="mt-3 grid gap-2">
            <ProviderRow label="Infrastructure Analysis" provider="Checkov" available={isInfraAvailable} missing={infrastructure?.missing_config} />
            <ProviderRow label="Vulnerability Analysis" provider="Trivy" available={isVulnAvailable} missing={vulnerability?.missing_config} />
            <ProviderRow label="Static Analysis" provider="SonarQube" available={isStaticConfigured} missing={staticAnalysis?.missing_config} />
            {(targetType === "azure") && (
              <ProviderRow label="Cloud Findings" provider="Azure Defender" available={cloudFindings?.available ?? false} missing={cloudFindings?.missing_config} />
            )}
            <p className="text-xs text-slate-500">
              {targetType === "aws"
                ? "AWS scans use Checkov for IaC, Trivy for vulnerabilities, and SonarQube for static code analysis."
                : targetType === "azure"
                  ? "Azure scans use Defender for cloud alerts, Checkov for IaC, Trivy for vulnerabilities, and SonarQube for static code analysis."
                  : targetType === "git"
                    ? "Repository scans use Trivy and Checkov, plus SonarQube if a project is configured."
                    : "Local scans use Checkov and Trivy, plus SonarQube if a project is configured."}
            </p>
          </div>
        ) : (
          <p className="mt-1 text-xs text-slate-500">
            {availableCount} of {scanners.length} providers available. SonarQube and Azure Defender require environment configuration.
          </p>
        )}
      </div>

      <label className="text-sm font-medium">
        Framework (optional)
        <input className="control mt-1" disabled={submitting} value={framework} onChange={(event) => setFramework(event.target.value)} placeholder="ISO/IEC 27001:2022 Annex A" />
      </label>

      {message ? <div className="rounded-md bg-panel px-3 py-2 text-sm text-slate-700">{message}</div> : null}
      {submitting ? (
        <div className="flex items-center gap-2 rounded-md border border-brand-100 bg-brand-50 px-3 py-2 text-sm text-brand-700">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Running security scan and generating compliance decisions...
        </div>
      ) : null}

      <div className="flex items-center justify-end gap-2">
        <button className="icon-button" disabled={submitting} onClick={onClose}>
          Cancel
        </button>
        <button className="primary-button" disabled={submitting} onClick={submit}>
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Terminal className="h-4 w-4" aria-hidden />
          )}
          {submitting ? "Running..." : "Run scan"}
        </button>
      </div>
    </div>
  );
}

function ProviderRow({
  label,
  provider,
  available,
  missing,
}: {
  label: string;
  provider: string;
  available: boolean;
  missing?: string[] | null;
}) {
  return (
    <div className="flex items-center justify-between rounded-md border border-line bg-white px-3 py-2 text-sm">
      <div className="flex flex-col">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="text-xs text-slate-500">{provider}</span>
      </div>
      {available ? (
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
          <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden />
          Connected
        </span>
      ) : (
        <span className="text-xs text-slate-400">
          {missing && missing.length > 0 ? `Not configured: ${missing.join(", ")}` : "Not available"}
        </span>
      )}
    </div>
  );
}

function JsonEditor({
  disabled,
  label,
  rows,
  value,
  onChange,
}: {
  disabled?: boolean;
  label: string;
  rows: number;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <textarea
        className="control mt-1 w-full resize-y font-mono text-xs"
        disabled={disabled}
        rows={rows}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function SampleScanForm({
  onBusyChange,
  onCreated,
  onClose,
}: {
  onBusyChange: (busy: boolean) => void;
  onCreated: () => void;
  onClose: () => void;
}) {
  const [targetEnvironment, setTargetEnvironment] = useState("sample-iac");
  const [findingsJson, setFindingsJson] = useState(sampleFindings);
  const [failuresJson, setFailuresJson] = useState(sampleFailures);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    onBusyChange(submitting);
  }, [onBusyChange, submitting]);

  async function submit() {
    if (submitting) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const findings = JSON.parse(findingsJson);
      const failures = JSON.parse(failuresJson);
      const result = await api.scanRuns.create({
        target_environment: targetEnvironment,
        findings,
        scanner_failures: failures,
      });
      setMessage(`Created sample scan run ${result.id}.`);
      onCreated();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to create sample scan.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-3">
      <label className="text-sm font-medium">
        Target environment
        <input
          className="control mt-1"
          disabled={submitting}
          value={targetEnvironment}
          onChange={(event) => setTargetEnvironment(event.target.value)}
          placeholder="sample-iac"
        />
      </label>
      <JsonEditor disabled={submitting} label="Findings JSON" rows={8} value={findingsJson} onChange={setFindingsJson} />
      <JsonEditor disabled={submitting} label="Scanner failures JSON (optional)" rows={4} value={failuresJson} onChange={setFailuresJson} />
      {message ? <div className="rounded-md bg-panel px-3 py-2 text-sm text-slate-700">{message}</div> : null}
      {submitting ? (
        <div className="flex items-center gap-2 rounded-md border border-brand-100 bg-brand-50 px-3 py-2 text-sm text-brand-700">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Creating scan, mapping findings, and generating compliance decisions...
        </div>
      ) : null}
      <div className="flex items-center justify-end gap-2">
        <button className="icon-button" disabled={submitting} onClick={onClose}>
          Cancel
        </button>
        <button className="primary-button" disabled={submitting} onClick={submit}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
          {submitting ? "Running..." : "Run sample scan"}
        </button>
      </div>
    </div>
  );
}
