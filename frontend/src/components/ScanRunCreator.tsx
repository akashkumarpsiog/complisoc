import { useEffect, useState, type ReactNode } from "react";
import { Cloud, Folder, Loader2, Play, Terminal, X } from "lucide-react";
import { api } from "../services/api";
import type { ScannerInfo } from "../types";
import { sampleFailures, sampleFindings } from "../services/json";

type Mode = "live" | "sample";
type EnvironmentPreset = "local" | "aws" | "azure";

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
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [preset, setPreset] = useState<EnvironmentPreset>("local");
  const [target, setTarget] = useState(".");
  const [framework, setFramework] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void api.scanners.list().then((items) => {
      setScanners(items);
      setSelected(new Set(items.filter((item) => item.available && item.kind !== "cloud").map((item) => item.name)));
    });
  }, []);

  useEffect(() => {
    onBusyChange(submitting);
  }, [onBusyChange, submitting]);

  async function submit() {
    if (submitting) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const result = await api.scans.run({
        target,
        scanners: selected.size ? [...selected] : undefined,
        framework: framework.trim() || undefined,
      });
      setMessage(`Created scan run ${result.id} from live scanners.`);
      onCreated();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to run scan.");
    } finally {
      setSubmitting(false);
    }
  }

  function toggle(name: string, available: boolean) {
    if (!available || submitting) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  function applyPreset(nextPreset: EnvironmentPreset) {
    if (submitting) return;
    setPreset(nextPreset);
    const names =
      nextPreset === "aws"
        ? ["checkov", "trivy", "sonarqube"]
        : nextPreset === "azure"
          ? ["defender", "checkov"]
          : scanners.filter((item) => item.kind !== "cloud").map((item) => item.name);
    setSelected(new Set(scanners.filter((item) => item.available && names.includes(item.name)).map((item) => item.name)));
    if (nextPreset === "local") setTarget(".");
    if (nextPreset === "aws") setTarget("aws-iac-container");
    if (nextPreset === "azure") setTarget("azure-subscription");
  }

  const targetLabel =
    preset === "azure" ? "Azure subscription or resource scope" : preset === "aws" ? "AWS IaC/container target" : "Target path";
  const targetPlaceholder =
    preset === "azure" ? "azure-subscription or resource group label" : preset === "aws" ? "C:/repo, ./terraform, or image/project label" : ". or C:/repo";

  return (
    <div className="grid gap-3">
      <div>
        <div className="mb-1 text-sm font-medium">Environment</div>
        <div className="grid gap-2 md:grid-cols-3">
          <PresetButton active={preset === "local"} disabled={submitting} icon={<Folder className="h-4 w-4" />} label="Local" onClick={() => applyPreset("local")} />
          <PresetButton active={preset === "aws"} disabled={submitting} icon={<Cloud className="h-4 w-4" />} label="AWS IaC" onClick={() => applyPreset("aws")} />
          <PresetButton active={preset === "azure"} disabled={submitting} icon={<Cloud className="h-4 w-4" />} label="Azure" onClick={() => applyPreset("azure")} />
        </div>
      </div>

      <label className="text-sm font-medium">
        {targetLabel}
        <input className="control mt-1" disabled={submitting} value={target} onChange={(event) => setTarget(event.target.value)} placeholder={targetPlaceholder} />
      </label>

      <div>
        <div className="mb-1 text-sm font-medium">Scanners</div>
        <div className="grid gap-2 md:grid-cols-2">
          {scanners.map((item) => {
            const checked = selected.has(item.name);
            return (
              <button
                key={item.name}
                type="button"
                disabled={submitting || !item.available}
                onClick={() => toggle(item.name, item.available)}
                className={`rounded-md border px-3 py-2 text-left text-sm transition ${
                  !item.available
                    ? "cursor-not-allowed border-line bg-panel text-slate-400"
                    : checked
                      ? "border-brand-200 bg-brand-50 text-brand-700"
                      : "border-line bg-white text-slate-600"
                }`}
              >
                <span className="flex items-center gap-2 font-medium">
                  <span className={`h-2 w-2 rounded-full ${item.available ? "bg-emerald-500" : "bg-slate-300"}`} />
                  {item.label || item.name}
                  <span className="text-xs uppercase text-slate-400">{item.kind || "local"}</span>
                </span>
                {item.description ? <span className="mt-1 block text-xs font-normal text-slate-500">{item.description}</span> : null}
                {!item.available && item.missing_config?.length ? (
                  <span className="mt-1 block text-xs font-normal text-slate-400">Needs: {item.missing_config.join(", ")}</span>
                ) : null}
              </button>
            );
          })}
          {scanners.length === 0 ? <span className="text-sm text-slate-500">Loading scanners...</span> : null}
        </div>
        {preset === "aws" ? (
          <p className="mt-2 text-xs text-slate-500">AWS support follows the requirements: scan IaC/container assets with Checkov, Trivy, and SonarQube.</p>
        ) : null}
        {preset === "azure" ? (
          <p className="mt-2 text-xs text-slate-500">
            Azure support uses Microsoft Defender when AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, and AZURE_SUBSCRIPTION_ID are configured.
          </p>
        ) : null}
      </div>

      <label className="text-sm font-medium">
        Framework (optional)
        <input className="control mt-1" disabled={submitting} value={framework} onChange={(event) => setFramework(event.target.value)} placeholder="ISO/IEC 27001:2022 Annex A" />
      </label>

      {message ? <div className="rounded-md bg-panel px-3 py-2 text-sm text-slate-700">{message}</div> : null}
      {submitting ? (
        <div className="flex items-center gap-2 rounded-md border border-brand-100 bg-brand-50 px-3 py-2 text-sm text-brand-700">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Running scanners, mapping findings, and generating compliance decisions...
        </div>
      ) : null}

      <div className="flex items-center justify-end gap-2">
        <button className="icon-button" disabled={submitting} onClick={onClose}>
          Cancel
        </button>
        <button className="primary-button" disabled={submitting} onClick={submit}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Terminal className="h-4 w-4" aria-hidden />}
          {submitting ? "Running..." : "Run scan"}
        </button>
      </div>
    </div>
  );
}

function PresetButton({
  active,
  disabled,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  disabled: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium ${
        active ? "border-brand-200 bg-brand-50 text-brand-700" : "border-line bg-white text-slate-600"
      }`}
    >
      {icon}
      {label}
    </button>
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
