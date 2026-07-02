import { useState } from "react";
import { Play } from "lucide-react";
import { api } from "../services/api";
import { parseFailureJson, parseFindingJson, sampleFailures, sampleFindings } from "../services/json";

export function ScanRunCreator({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState("aws-iac");
  const [findingsJson, setFindingsJson] = useState(sampleFindings);
  const [failuresJson, setFailuresJson] = useState(sampleFailures);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    setMessage(null);
    try {
      const findings = parseFindingJson(findingsJson);
      const scanner_failures = parseFailureJson(failuresJson);
      const result = await api.scanRuns.create({ target_environment: target, findings, scanner_failures });
      setMessage(`Created scan run ${result.id}.`);
      onCreated();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to create scan run.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <button className="primary-button" onClick={() => setOpen((value) => !value)}>
        <Play className="h-4 w-4" aria-hidden />
        New sample scan
      </button>
      {open ? (
        <div className="absolute right-4 top-28 z-20 w-[min(720px,calc(100vw-2rem))] rounded-lg border border-line bg-white p-4 shadow-xl">
          <div className="grid gap-3">
            <label className="text-sm font-medium">
              Target environment
              <input className="control mt-1 w-full" value={target} onChange={(event) => setTarget(event.target.value)} />
            </label>
            <JsonEditor label="Findings JSON" rows={12} value={findingsJson} onChange={setFindingsJson} />
            <JsonEditor label="Scanner failures JSON" rows={5} value={failuresJson} onChange={setFailuresJson} />
            {message ? <div className="rounded-md bg-panel px-3 py-2 text-sm text-slate-700">{message}</div> : null}
            <div className="flex justify-end gap-2">
              <button className="icon-button" onClick={() => setOpen(false)}>
                Close
              </button>
              <button className="primary-button" disabled={submitting} onClick={submit}>
                <Play className="h-4 w-4" aria-hidden />
                Create
              </button>
            </div>
          </div>
        </div>
      ) : null}
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
