import { RefreshCw, ShieldCheck } from "lucide-react";
import { StatusBadge } from "./Primitives";
import { navigation, type ViewId } from "../navigation";

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
  const active = navigation.find((item) => item.id === view) || navigation[0];
  return (
    <div className="min-h-screen bg-[#eef2f7]">
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-line bg-white lg:flex">
        <div className="flex items-center gap-3 border-b border-line px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            <ShieldCheck className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <div className="text-lg font-semibold leading-tight text-ink">Complisoc</div>
            <div className="text-xs text-slate-500">Compliance intelligence</div>
          </div>
        </div>
        <Nav view={view} onViewChange={onViewChange} />
        <div className="mt-auto border-t border-line px-5 py-3 text-xs text-slate-400">
          v0.1 · deterministic mapping
        </div>
      </aside>

      <main className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-line bg-white/90 px-4 py-3 backdrop-blur md:px-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-xl font-semibold text-ink">{active.label}</h1>
              <p className="mt-0.5 text-sm text-slate-500">{active.description}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge value={`api ${apiStatus}`} />
              <StatusBadge value={`db ${dbStatus}`} />
              <button className="primary-button" onClick={onRefresh}>
                <RefreshCw className="h-4 w-4" aria-hidden />
                Refresh
              </button>
            </div>
          </div>
          <div className="mt-3 flex gap-2 overflow-x-auto lg:hidden">
            {navigation.map((item) => (
              <button
                className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-medium transition ${
                  view === item.id ? "bg-brand-600 text-white" : "bg-panel text-slate-600"
                }`}
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
    <nav className="flex-1 space-y-1 overflow-y-auto p-3">
      {navigation.map((item) => {
        const Icon = item.icon;
        const isActive = view === item.id;
        return (
          <button
            className={`relative flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm font-medium transition ${
              isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-panel"
            }`}
            key={item.id}
            onClick={() => onViewChange(item.id)}
          >
            {isActive ? <span className="absolute inset-y-1.5 left-0 w-1 rounded-full bg-brand-600" aria-hidden /> : null}
            <Icon className="h-4 w-4" aria-hidden />
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}
