import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Cloud, Folder, GitBranch, Loader2, Terminal, X } from "lucide-react";
import { api } from "../services/api";
import type { ScanRun, ScannerInfo } from "../types";
import { staggerStyle } from "./Primitives";

type TargetType = "local" | "git" | "azure";

const TARGET_OPTIONS: { value: TargetType; label: string; icon: ReactNode }[] = [
  { value: "local", label: "Local File / Folder", icon: <Folder className="h-4 w-4" aria-hidden /> },
  { value: "git", label: "Git Repository", icon: <GitBranch className="h-4 w-4" aria-hidden /> },
  { value: "azure", label: "Azure Defender", icon: <Cloud className="h-4 w-4" aria-hidden /> },
];

export function ScanRunCreator({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (scanRun: ScanRun) => void | Promise<void>;
}) {
  const [busy, setBusy] = useState(false);

  function close() {
    onOpenChange(false);
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 animate-fade-in">
      <div className="absolute inset-0 bg-ink/30 backdrop-blur-sm transition-opacity duration-200" onClick={close} />
      <div className="relative max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-line bg-white shadow-2xl animate-scale-in">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-white/95 backdrop-blur-sm px-6 py-4">
          <h2 className="text-lg font-semibold text-ink">Run scan</h2>
          <button className="icon-button !border-0 !p-1.5 text-subtle hover:text-ink hover:bg-panel-hover" onClick={close} aria-label={busy ? "Cancel scan and close" : "Close"}>
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-6">
          <LiveScanForm onBusyChange={setBusy} onCreated={onCreated} onClose={() => onOpenChange(false)} />
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
  onCreated: (scanRun: ScanRun) => void | Promise<void>;
  onClose: () => void;
}) {
  const [scanners, setScanners] = useState<ScannerInfo[]>([]);
  const [targetType, setTargetType] = useState<TargetType>("local");
  const [target, setTarget] = useState(".");
  const [framework, setFramework] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showProviders, setShowProviders] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const abortController = useRef<AbortController | null>(null);
  const scanStartedAt = useRef<number | null>(null);

  useEffect(() => () => abortController.current?.abort(), []);

  useEffect(() => {
    if (!submitting || scanStartedAt.current === null) return;
    const timer = window.setInterval(() => {
      const start = scanStartedAt.current;
      if (start !== null) setElapsedSeconds(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [submitting]);

  useEffect(() => {
    void api.scanners.list().then(setScanners);
  }, []);

  useEffect(() => {
    onBusyChange(submitting);
  }, [onBusyChange, submitting]);

  useEffect(() => {
    if (targetType === "local") setTarget("scan_targets/terraform");
    if (targetType === "azure") setTarget("azure-subscription");
    if (targetType === "git") setTarget("");
  }, [targetType]);

  const scannerMap = Object.fromEntries(scanners.map((s) => [s.name, s]));
  const isCloud = targetType === "azure";

  const infrastructure = scannerMap.checkov;
  const vulnerability = scannerMap.trivy;
  const staticAnalysis = scannerMap.sonarqube;
  const cloudFindings = scannerMap.defender;

  const isStaticConfigured = staticAnalysis?.available ?? false;
  const isInfraAvailable = infrastructure?.available ?? false;
  const isVulnAvailable = vulnerability?.available ?? false;
  const applicableScanners = isCloud ? [cloudFindings] : [infrastructure, vulnerability, staticAnalysis];
  const availableCount = applicableScanners.filter((scanner) => scanner?.available).length;

  async function submit() {
    if (submitting) return;
    setSubmitting(true);
    setMessage(null);
    setElapsedSeconds(0);
    scanStartedAt.current = Date.now();
    const controller = new AbortController();
    abortController.current = controller;
    try {
      const result = await api.scans.run({
        target,
        scan_profile: targetType,
        framework: framework.trim() || undefined,
      }, controller.signal);
      await onCreated(result);
      onClose();
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        setMessage(err instanceof Error ? err.message : "Unable to run scan.");
      }
    } finally {
      abortController.current = null;
      scanStartedAt.current = null;
      setSubmitting(false);
    }
  }

  const targetLabel =
    targetType === "git" ? "Repository path or URL (the local clone is scanned)" : "Local file or folder path";
  const targetPlaceholder =
    targetType === "git" ? "owner/repo or C:/path/to/repo" : ". or C:/path/to/folder or C:/path/to/file.tf";

  return (
    <div className="grid gap-5">
      <div>
        <label className="text-sm font-semibold text-ink block mb-2">Target</label>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {TARGET_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={submitting}
              onClick={() => setTargetType(option.value)}
              className={`inline-flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-medium transition-all duration-150 ${
                targetType === option.value
                  ? "border-brand-200 bg-brand-50 text-brand-700 shadow-sm shadow-brand-500/5"
                  : "border-line bg-white text-muted hover:border-line-strong hover:bg-panel-hover hover:text-ink"
              }`}
            >
              {option.icon}
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {isCloud ? (
        <div className="rounded-xl border border-line bg-panel/40 px-4 py-3">
          <p className="text-sm font-semibold text-ink">Azure subscription</p>
          <p className="text-xs text-muted mt-0.5">
            Microsoft Defender for Cloud reads findings from your configured Azure subscription.
          </p>
        </div>
      ) : (
        <label className="text-sm font-semibold text-ink block">
          {targetLabel}
          <input className="control mt-1.5" disabled={submitting} value={target} onChange={(event) => setTarget(event.target.value)} placeholder={targetPlaceholder} />
        </label>
      )}

      {isCloud ? (
        <div className="flex items-center gap-2 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm font-semibold text-brand-700">
          <Cloud className="h-4 w-4" aria-hidden />
          <span>Reads alerts, security recommendations, and secure scores from the configured Azure subscription.</span>
        </div>
      ) : (
        <div className="flex items-center gap-2 rounded-xl border border-line bg-panel/50 px-4 py-3 text-sm font-semibold text-ink">
          <Cloud className="h-4 w-4" aria-hidden />
          <span>Local file scan — analyzes the path below. No live cloud connection is made.</span>
        </div>
      )}

      <div className="rounded-xl border border-line bg-panel/40 overflow-hidden">
        <button
          type="button"
          onClick={() => setShowProviders((prev) => !prev)}
          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold text-ink hover:bg-white transition-colors duration-150"
        >
          <span>What this scan will do</span>
          {showProviders ? <ChevronDown className="h-4 w-4 text-subtle" /> : <ChevronRight className="h-4 w-4 text-subtle" />}
        </button>
        {showProviders ? (
          <div className="border-t border-line bg-white p-4 grid gap-3">
            {!isCloud && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-subtle mb-2">Local analysis (scans the path below)</p>
                <div className="grid gap-2.5">
                  <ProviderRow label="Infrastructure Analysis" provider="Checkov" kind="local" available={isInfraAvailable} missing={infrastructure?.missing_config} index={0} />
                  <ProviderRow label="Vulnerability Analysis" provider="Trivy" kind="local" available={isVulnAvailable} missing={vulnerability?.missing_config} index={1} />
                  <ProviderRow label="Static Analysis" provider="SonarQube" kind="local" available={isStaticConfigured} missing={staticAnalysis?.missing_config} index={2} />
                </div>
              </div>
            )}
            {isCloud && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-subtle mb-2">Live cloud (connects to your account)</p>
                <div className="grid gap-2.5">
                  <ProviderRow label="Cloud Findings" provider="Azure Defender" kind="cloud" available={cloudFindings?.available ?? false} missing={cloudFindings?.missing_config} index={3} />
                </div>
              </div>
            )}
            <p className="text-xs text-muted pt-1">
              {isCloud
                ? "Findings are then processed by the compliance mapping workflow."
                : targetType === "git"
                  ? "Repository scans use Trivy and Checkov, plus SonarQube if a project is configured."
                  : "Local scans use Checkov and Trivy, plus SonarQube if a project is configured."}
            </p>
          </div>
        ) : (
          <div className="px-4 py-2.5 text-xs text-muted border-t border-line">
            {availableCount} of {applicableScanners.length} providers available for this target.
          </div>
        )}
      </div>

      <label className="text-sm font-semibold text-ink block">
        Framework <span className="font-normal text-subtle">(optional)</span>
        <input className="control mt-1.5" disabled={submitting} value={framework} onChange={(event) => setFramework(event.target.value)} placeholder="ISO/IEC 27001:2022 Annex A" />
      </label>

      {message && (
        <div className={`rounded-xl border px-4 py-3 text-sm font-medium animate-slide-up ${message.includes("Created") ? "border-success/20 bg-success-light text-success-dark" : "border-danger/20 bg-danger-light text-danger-dark"}`}>
          {message}
        </div>
      )}
      {submitting && (
        <div role="status" aria-live="polite" className="flex items-start gap-3 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm font-medium text-brand-700">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          <div>
            <p>
              Scan is running · {String(Math.floor(elapsedSeconds / 60)).padStart(2, "0")}:
              {String(elapsedSeconds % 60).padStart(2, "0")} elapsed
            </p>
          </div>
        </div>
      )}

      <div className="flex items-center justify-end gap-2 pt-2">
        <button className="secondary-button" onClick={onClose}>
          {submitting ? "Cancel scan" : "Cancel"}
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
  kind = "local",
  scope,
  index = 0,
}: {
  label: string;
  provider: string;
  available: boolean;
  missing?: string[] | null;
  kind?: string;
  scope?: string | null;
  index?: number;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-line bg-white px-4 py-3 text-sm animate-fade-in hover:border-line-strong hover:shadow-sm transition-all duration-150" style={staggerStyle(index, 80)}>
      <div className="flex flex-col">
        <span className="font-semibold text-ink">{label}</span>
        <span className="text-xs text-subtle">
          {provider}
          {kind === "cloud" && (
            <span className="ml-2 inline-flex items-center rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-brand-700">
              Live
            </span>
          )}
          {scope && <span className="ml-1 text-subtle">· {scope}</span>}
        </span>
      </div>
      {available ? (
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-success">
          <span className="h-2 w-2 rounded-full bg-success shadow-sm shadow-success/30" aria-hidden />
          Connected
        </span>
      ) : (
        <span className="text-xs text-subtle">
          {missing && missing.length > 0 ? `Not configured: ${missing.join(", ")}` : "Not available"}
        </span>
      )}
    </div>
  );
}
