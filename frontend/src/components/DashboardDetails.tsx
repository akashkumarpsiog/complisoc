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
  return (
    <div className="rounded-xl border border-line bg-panel/40 overflow-hidden transition-all duration-200">
      <button
        onClick={toggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold text-ink hover:bg-white transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-500"
        aria-expanded={open}
      >
        <span className="inline-flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
          </span>
          Remediation steps
        </span>
        {open ? <ChevronUp className="h-4 w-4 text-subtle" /> : <ChevronDown className="h-4 w-4 text-subtle" />}
      </button>
      {open && (
        <div className="overflow-hidden border-t border-line bg-white transition-all duration-300 ease-in-out">
          <div className="p-4">
            {loading && <LoadingState label="Generating guidance" />}
            {error && <ErrorState message={error} onRetry={() => void load()} />}
            {result && (
              <>
                <ol className="space-y-3">
                  {result.steps.map((step, index) => (
                    <li key={step} className="flex gap-3 text-sm text-ink/90 leading-relaxed">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-bold text-brand-700 mt-0.5">
                        {index + 1}
                      </span>
                      <span className="flex-1">{step}</span>
                    </li>
                  ))}
                </ol>
                <p className="mt-4 text-xs text-subtle border-t border-line pt-3">
                  Source: {result.source === "groq" ? "AI-generated guidance" : "Deterministic fallback guidance"}
                </p>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
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
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/20 p-0 sm:p-4 animate-fade-in" role="dialog" aria-modal="true" aria-label="Control drill-down" onMouseDown={onClose}>
      <aside className="h-full w-full max-w-xl overflow-y-auto bg-white shadow-2xl animate-slide-in-right" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-line bg-white/95 backdrop-blur-sm px-6 py-5">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-brand-600">Control detail</p>
            <h2 className="mt-1.5 text-lg font-bold text-ink tracking-tight">
              {data ? `${data.control.control_id} · ${data.control.title}` : "Loading control"}
            </h2>
          </div>
          <button ref={closeButton} className="icon-button !border-0 !p-1.5 text-subtle hover:text-ink hover:bg-panel-hover" onClick={onClose} aria-label="Close control details">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-5 p-6">
          {loading && <LoadingState label="Loading control details" />}
          {error && <ErrorState message={error} onRetry={() => void load()} />}
          {data && (
            <>
              <p className="text-sm leading-relaxed text-muted">{data.control.description}</p>
              <div className="inline-flex items-center gap-2 rounded-lg bg-panel px-3 py-1.5 text-xs font-semibold text-subtle">
                <span>{data.control.framework_name}</span>
                <span className="h-1 w-1 rounded-full bg-line-strong" />
                <span>{data.items.length} unresolved finding{data.items.length === 1 ? "" : "s"}</span>
              </div>
              <div className="space-y-3 pt-2">
                {data.items.map((item) => (
                  <article key={item.mapping_id} className="rounded-xl border border-line bg-white p-5 shadow-sm transition-shadow duration-200 hover:shadow-md">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-ink truncate">{item.resource_identifier}</p>
                        <p className="mt-1 text-sm text-muted">
                          {item.severity} severity · Gemini {formatPercent(item.gemini_confidence)}
                        </p>
                      </div>
                      <StatusBadge value={item.status} />
                    </div>
                    <div className="mt-4">
                      <RemediationSuggestionPanel item={item} />
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
