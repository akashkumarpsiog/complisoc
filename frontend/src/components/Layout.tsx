import { Activity, Archive, ClipboardCheck, FileJson, Gauge, GitBranch, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { API_BASE_URL } from "../services/api";
import { StatusBadge } from "./Primitives";

export type ViewId = "overview" | "scan-runs" | "findings" | "mappings" | "controls" | "review" | "reports" | "bundles";

export const navigation: Array<{ id: ViewId; label: string; icon: typeof Gauge }> = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "scan-runs", label: "Scan Runs", icon: Activity },
  { id: "findings", label: "Findings", icon: Search },
  { id: "mappings", label: "Mappings", icon: GitBranch },
  { id: "controls", label: "Controls", icon: ShieldCheck },
  { id: "review", label: "Review Queue", icon: ClipboardCheck },
  { id: "reports", label: "Reports", icon: FileJson },
  { id: "bundles", label: "Audit Bundles", icon: Archive },
];

export function Layout({
  view,
  apiStatus,
  dbStatus,
  onViewChange,
  onRefresh,
  children,
}: {
  view: ViewId;
  apiStatus: string;
  dbStatus: string;
  onViewChange: (view: ViewId) => void;
  onRefresh: () => void;
  children: React.ReactNode;
}) {
  const title = navigation.find((item) => item.id === view)?.label || "Overview";
  return (
    <div className="min-h-screen bg-[#eef3f7]">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-line bg-white lg:block">
        <div className="border-b border-line px-5 py-4">
          <div className="text-lg font-semibold text-ink">Complisoc</div>
          <div className="mt-1 text-xs text-slate-500">Compliance intelligence</div>
        </div>
        <Nav view={view} onViewChange={onViewChange} />
      </aside>

      <main className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-line bg-white/95 px-4 py-3 backdrop-blur md:px-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-xl font-semibold text-ink">{title}</h1>
              <p className="mt-1 text-sm text-slate-600">{API_BASE_URL}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge value={`api ${apiStatus}`} />
              <StatusBadge value={`db ${dbStatus}`} />
              <button className="icon-button" onClick={onRefresh}>
                <RefreshCw className="h-4 w-4" aria-hidden />
                Refresh
              </button>
            </div>
          </div>
          <div className="mt-3 flex gap-2 overflow-x-auto lg:hidden">
            {navigation.map((item) => (
              <button
                className={`shrink-0 rounded-md px-3 py-2 text-sm font-medium ${view === item.id ? "bg-ink text-white" : "bg-panel text-slate-700"}`}
                key={item.id}
                onClick={() => onViewChange(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </header>
        <div className="space-y-5 p-4 md:p-6">{children}</div>
      </main>
    </div>
  );
}

function Nav({ view, onViewChange }: { view: ViewId; onViewChange: (view: ViewId) => void }) {
  return (
    <nav className="space-y-1 p-3">
      {navigation.map((item) => {
        const Icon = item.icon;
        return (
          <button
            className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm font-medium ${view === item.id ? "bg-ink text-white" : "text-slate-700 hover:bg-panel"}`}
            key={item.id}
            onClick={() => onViewChange(item.id)}
          >
            <Icon className="h-4 w-4" aria-hidden />
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}
