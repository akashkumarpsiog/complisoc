import { useEffect, useState } from "react";
import { Play, Terminal, X } from "lucide-react";
import { api } from "../services/api";
import type { ScannerInfo } from "../types";
import { parseFailureJson, parseFindingJson, sampleFailures, sampleFindings } from "../services/json";

type Mode = "live" | "sample";

export function ScanRunCreator({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("live");

  if (!open) {
    return (
      <button className="primary-button" onClick={() => setOpen(true)}>
        <Play className="h-4 w-4" aria-hidden />
        New scan
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={() => setOpen(false)} />
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-line bg-white shadow-xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-white px-4 py-3">
          <div className="flex gap-2">
            <button
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                mode === "live" ? "bg-brand-600 text-white" : "bg-panel text-slate-600 hover:bg-slate-100"
              }`}
              onClick={() => setMode("live")}
            >
              Live scan
            </button>
            <button
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                mode === "sample" ? "bg-brand-600 text-white" : "bg-panel text-slate-600 hover:bg-slate-100"
              }`}
              onClick={() => setMode("sample")}
            >
              Sample scan
            </button>
          </div>
          <button className="icon-button border-0 p-1" onClick={() => setOpen(false)} aria-label="Close">
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <div className="p-4">
          {mode === "live" ? <LiveScanForm onCreated={onCreated} onClose={() => setOpen(false)} /> : <SampleScanForm onCreated={onCreated} onClose={() => setOpen(false)} />}
        </div>
      </div>
    </div>
  );
}

function LiveScanForm({ onCreated, onClose }: { onCreated: () => void; onClose: () => void }) {
  const [scanners, setScanners] = useState<ScannerInfo[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [target, setTarget] = useState(".");
  const [framework, setFramework] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void api.scanners.list().then((items) => {
      setScanners(items);
      setSelected(new Set(items.filter((item) => item.available).map((item) => item.name)));
    });
  }, []);

  async function submit() {
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
    if (!available) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  return (
    <div className="grid gap-3">
      <label className="text-sm font-medium">
        Target path
        <input className="control mt-1" value={target} onChange={(event) => setTarget(event.target.value)} placeholder=". or C:/repo" />
      </label>

      <div>
        <div className="mb-1 text-sm font-medium">Scanners</div>
        <div className="flex flex-wrap gap-2">
          {scanners.map((item) => {
            const checked = selected.has(item.name);
            return (
              <button
                key={item.name}
                type="button"
                onClick={() => toggle(item.name, item.available)}
                className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition ${
                  !item.available
                    ? "cursor-not-allowed border-line bg-panel text-slate-400"
                    : checked
                      ? "border-brand-200 bg-brand-50 text-brand-700"
                      : "border-line bg-white text-slate-600"
                }`}
              >
                <span className={`h-2 w-2 rounded-full ${item.available ? "bg-emerald-500" : "bg-slate-300"}`} />
                {item.name}
                {!item.available ? <span className="text-xs text-slate-400">(unavailable)</span> : null}
              </button>
            );
          })}
          {scanners.length === 0 ? <span className="text-sm text-slate-500">Loading scanners…</span> : null}
        </div>
      </div>

      <label className="text-sm font-medium">
        Framework (optional)
        <input className="control mt-1" value={framework} onChange={(event) => setFramework(event.target.value)} placeholder="ISO/IEC 27001:2022 Annex A" />
      </label>

      {message ? <div className="rounded-md bg-panel px-3 py-2 text-sm text-slate-700">{message}</div> : null}

      <div className="flex items-center justify-end gap-2">
        <button className="icon-button" onClick={onClose}>
          Cancel
        </button>
        <button className="primary-button" disabled={submitting} onClick={submit}>
          <Terminal className="h-4 w-4" aria-hidden />
          Run scan
        </button>
      </div>
    </div>
  );
}

function JsonEditor({
  label,
  rows,
  value,
  onChange,
}: {
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
        rows={rows}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
