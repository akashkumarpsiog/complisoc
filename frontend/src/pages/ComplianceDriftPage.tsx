import { useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { ScanDiff } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, Section, StatusBadge } from "../components/Primitives";
import { formatDate } from "../utils/format";

export function ComplianceDriftPage({ onViewChange }: { onViewChange?: (viewId: string) => void }) {
  const [scanRunId, setScanRunId] = useState("");
  const [compareToId, setCompareToId] = useState("");
  const [selectedScanId, setSelectedScanId] = useState<number | null>(null);
  const scanRuns = useResource(api.scanRuns.list);
  const drift = useResource(() => (scanRunId && parseInt(scanRunId, 10) ? api.dashboard.drift(parseInt(scanRunId, 10), compareToId ? parseInt(compareToId, 10) : undefined) : Promise.reject("No scan selected")), [scanRunId, compareToId]);

  const handleAnalyze = () => {
    if (!scanRunId) return;
    setSelectedScanId(parseInt(scanRunId, 10));
  };

  return (
    <Section
      title="Compliance Drift"
      description="Compare scan runs to see how compliance posture changed"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <select className="control" value={scanRunId} onChange={(e) => setScanRunId(e.target.value)}>
            <option value="">Current scan</option>
            {(scanRuns.data || []).filter((s) => s.status === "completed").map((scanRun) => (
              <option key={scanRun.id} value={scanRun.id}>
                #{scanRun.id} {scanRun.target_environment} ({formatDate(scanRun.created_at)})
              </option>
            ))}
          </select>
          <select className="control" value={compareToId} onChange={(e) => setCompareToId(e.target.value)}>
            <option value="">Previous scan (auto)</option>
            {(scanRuns.data || []).filter((s) => s.status === "completed" && s.id !== parseInt(scanRunId, 10)).map((scanRun) => (
              <option key={scanRun.id} value={scanRun.id}>
                #{scanRun.id} {scanRun.target_environment} ({formatDate(scanRun.created_at)})
              </option>
            ))}
          </select>
          <button className="icon-button" disabled={!scanRunId} onClick={handleAnalyze}>
            Analyze drift
          </button>
        </div>
      }
    >
      {!selectedScanId ? (
        <div className="text-sm text-muted">Select a completed scan run and click Analyze drift to compare.</div>
      ) : (
        <ResourceBoundary resource={drift}>
          {(data) => <DriftResults data={data} />}
        </ResourceBoundary>
      )}
    </Section>
  );
}

function DriftResults({ data }: { data: ScanDiff }) {
  if (data.previous_scan_id === null) {
    return (
      <div className="space-y-6">
        <div className="rounded-xl border border-brand/20 bg-brand-light p-5">
          <h3 className="text-sm font-bold text-brand-dark">Baseline scan</h3>
          <p className="mt-1 text-sm text-muted">
            This is the first completed scan. All {data.current_finding_count} findings are treated as new. Run another scan to see drift.
          </p>
        </div>
        <FindingTable findings={data.new_findings} />
      </div>
    );
  }

  const severityOrder = ["critical", "high", "medium", "low", "info"];
  const severitySet = new Set<string>();
  for (const key of Object.keys(data.severity_new)) severitySet.add(key);
  for (const key of Object.keys(data.severity_resolved)) severitySet.add(key);
  const allSeverities = Array.from(severitySet).sort((a, b) => severityOrder.indexOf(a) - severityOrder.indexOf(b));

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="panel p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-subtle">Previous scan</div>
          <div className="mt-1 text-lg font-bold text-ink">#{data.previous_scan_id}</div>
          <div className="text-xs text-muted">{data.previous_finding_count} findings</div>
        </div>
        <div className="panel p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-subtle">Current scan</div>
          <div className="mt-1 text-lg font-bold text-ink">#{data.current_scan_id}</div>
          <div className="text-xs text-muted">{data.current_finding_count} findings</div>
        </div>
        <div className="panel p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-subtle">Net change</div>
          <div className={`mt-1 text-lg font-bold ${data.net_change > 0 ? "text-danger-dark" : data.net_change < 0 ? "text-success-dark" : "text-ink"}`}>
            {data.net_change > 0 ? `+${data.net_change}` : data.net_change}
          </div>
          <div className="text-xs text-muted">{data.new_count} new · {data.resolved_count} resolved</div>
        </div>
        <div className="panel p-4">
          <div className="text-xs font-bold uppercase tracking-wider text-subtle">Unchanged</div>
          <div className="mt-1 text-lg font-bold text-ink">{data.unchanged_count}</div>
          <div className="text-xs text-muted">Still present in both scans</div>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Section title="Severity drift" description="New vs resolved findings by severity">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[320px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-line-strong bg-panel/60 text-xs font-bold uppercase tracking-wider text-subtle">
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3 text-right">New</th>
                  <th className="px-4 py-3 text-right">Resolved</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {allSeverities.map((severity) => (
                  <tr key={severity} className="animate-fade-in">
                    <td className="px-4 py-3 font-semibold capitalize text-ink/80">{severity}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink/80">{data.severity_new[severity] || 0}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink/80">{data.severity_resolved[severity] || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section title="Control drift" description="Controls newly affected or recovered">
          <div className="space-y-4">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-subtle mb-2">Newly affected controls</h3>
              {data.new_control_ids.length === 0 ? (
                <p className="text-sm text-muted">No new controls affected.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {data.new_control_ids.map((cid) => (
                    <span key={cid} className="inline-flex items-center rounded-md border border-danger/20 bg-danger-light px-2.5 py-1 text-xs font-semibold text-danger-dark">
                      {cid}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-subtle mb-2">Recovered controls</h3>
              {data.resolved_control_ids.length === 0 ? (
                <p className="text-sm text-muted">No controls recovered.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {data.resolved_control_ids.map((cid) => (
                    <span key={cid} className="inline-flex items-center rounded-md border border-success/20 bg-success-light px-2.5 py-1 text-xs font-semibold text-success-dark">
                      {cid}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Section>
      </div>

      <Section title="Finding details" description="Inspect changed findings" collapsible defaultOpen={false}>
        <div className="space-y-4">
          <FindingTab title={`New (${data.new_findings.length})`} findings={data.new_findings} tone="danger" />
          <FindingTab title={`Resolved (${data.resolved_findings.length})`} findings={data.resolved_findings} tone="success" />
          <FindingTab title={`Unchanged (${data.unchanged_findings.length})`} findings={data.unchanged_findings} tone="brand" />
        </div>
      </Section>
    </div>
  );
}

function FindingTab({ title, findings, tone }: { title: string; findings: ScanDiff["new_findings"]; tone: "danger" | "success" | "brand" }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-line bg-white">
      <button
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold text-ink hover:bg-panel-hover transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-500"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="inline-flex items-center gap-2.5">
          <span className={`flex h-2 w-2 rounded-full ${tone === "danger" ? "bg-danger" : tone === "success" ? "bg-success" : "bg-brand"}`} aria-hidden />
          {title}
        </span>
        {open ? "▲" : "▼"}
      </button>
      {open && (
        <div className="border-t border-line px-4 py-4">
          {findings.length === 0 ? (
            <p className="text-sm text-muted">No findings in this category.</p>
          ) : (
            <FindingTable findings={findings} />
          )}
        </div>
      )}
    </div>
  );
}

function FindingTable({ findings }: { findings: ScanDiff["new_findings"] }) {
  return (
    <div className="overflow-x-auto -mx-4">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line-strong bg-panel/60 text-xs font-bold uppercase tracking-wider text-subtle">
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Scanner</th>
            <th className="px-4 py-3">Resource</th>
            <th className="px-4 py-3">Severity</th>
            <th className="px-4 py-3">Title</th>
            <th className="px-4 py-3">Controls</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {findings.map((item, idx) => (
            <tr key={item.fingerprint} className="animate-fade-in" style={{ animationDelay: `${idx * 30}ms` }}>
              <td className="px-4 py-3"><StatusBadge value={item.status} /></td>
              <td className="px-4 py-3 text-ink/80">{item.scanner_name}</td>
              <td className="px-4 py-3 text-ink/80 font-mono text-xs">{item.resource_identifier}</td>
              <td className="px-4 py-3 capitalize text-ink/80">{item.severity}</td>
              <td className="px-4 py-3 text-ink/90">{item.title}</td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {item.control_ids.slice(0, 3).map((cid) => (
                    <span key={cid} className="inline-flex items-center rounded border border-line bg-panel px-2 py-0.5 text-xs font-medium text-subtle">{cid}</span>
                  ))}
                  {item.control_ids.length > 3 && (
                    <span className="text-xs text-muted">+{item.control_ids.length - 3}</span>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
