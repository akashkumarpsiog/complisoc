import { ChevronDown, ChevronUp, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import type { ControlDrillDown, RemediationBacklog, RemediationSuggestion } from "../types";
import { formatPercent } from "../utils/format";
import { ErrorState, LoadingState, StatusBadge } from "./Primitives";

export function RemediationSuggestionPanel({ item }: { item: RemediationBacklog["items"][number] }) {
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState<RemediationSuggestion | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true); setError(null);
    try { setResult(await api.dashboard.suggestion(item.mapping_id)); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to generate remediation guidance."); }
    finally { setLoading(false); }
  };
  const toggle = () => {
    const next = !open; setOpen(next);
    if (next && !result && !loading) void load();
  };
  return <div className="rounded-lg border border-slate-200 bg-slate-50/70">
    <button onClick={toggle} className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-white focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-500" aria-expanded={open}>
      <span className="inline-flex items-center gap-2"><Sparkles className="h-4 w-4 text-brand-600" />Remediation steps</span>
      {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
    </button>
    {open && <div className="border-t border-slate-200 bg-white p-3">
      {loading && <LoadingState label="Generating guidance" />}
      {error && <ErrorState message={error} onRetry={() => void load()} />}
      {result && <><ol className="space-y-2">{result.steps.map((step, index) => <li key={step} className="flex gap-2 text-sm text-slate-700"><span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">{index + 1}</span>{step}</li>)}</ol><p className="mt-3 text-xs text-slate-500">Source: {result.source === "groq" ? "AI-generated guidance" : "Deterministic fallback guidance"}</p></>}
    </div>}
  </div>;
}

export function ControlDrillDownDrawer({ controlId, onClose }: { controlId: number | null; onClose: () => void }) {
  const [data, setData] = useState<ControlDrillDown | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const closeButton = useRef<HTMLButtonElement>(null);
  const load = async () => {
    if (controlId === null) return;
    setLoading(true); setError(null);
    try { setData(await api.dashboard.controlDrillDown(controlId)); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to load control details."); }
    finally { setLoading(false); }
  };
  useEffect(() => { setData(null); setError(null); if (controlId !== null) void load(); }, [controlId]);
  useEffect(() => {
    if (controlId === null) return;
    closeButton.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [controlId, onClose]);
  if (controlId === null) return null;
  return <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/30 p-0 sm:p-3" role="dialog" aria-modal="true" aria-label="Control drill-down" onMouseDown={onClose}>
    <aside className="h-full w-full max-w-xl overflow-y-auto bg-white shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
      <div className="sticky top-0 flex items-start justify-between border-b border-line bg-white px-5 py-4"><div><p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Control detail</p><h2 className="mt-1 text-lg font-semibold text-ink">{data ? `${data.control.control_id} · ${data.control.title}` : "Loading control"}</h2></div><button ref={closeButton} className="icon-button" onClick={onClose} aria-label="Close control details"><X className="h-4 w-4" /></button></div>
      <div className="space-y-4 p-5">{loading && <LoadingState label="Loading control details" />}{error && <ErrorState message={error} onRetry={() => void load()} />}{data && <><p className="text-sm leading-6 text-slate-600">{data.control.description}</p><p className="text-xs font-medium text-slate-500">{data.control.framework_name} · {data.items.length} unresolved finding{data.items.length === 1 ? "" : "s"}</p>{data.items.map((item) => <article className="rounded-xl border border-slate-200 p-4" key={item.mapping_id}><div className="flex items-start justify-between gap-3"><div><p className="font-medium text-slate-800">{item.resource_identifier}</p><p className="mt-1 text-sm text-slate-600">{item.severity} severity · Gemini {formatPercent(item.gemini_confidence)}</p></div><StatusBadge value={item.status} /></div><div className="mt-3"><RemediationSuggestionPanel item={item} /></div></article>)}</>}</div>
    </aside>
  </div>;
}
