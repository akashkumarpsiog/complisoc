import { RefreshCw, ShieldCheck, Menu, X } from "lucide-react";
import { useState } from "react";
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
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const active = navigation.find((item) => item.id === view) || navigation[0];

  return (
    <div className="flex flex-col lg:h-screen lg:flex-row lg:overflow-hidden">
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/20 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={[
          "fixed inset-y-0 left-0 z-40 w-64 flex-col border-r border-line bg-white transition-transform duration-200 ease-in-out lg:static lg:z-10 lg:translate-x-0 lg:flex lg:h-full",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
      >
        <div className="flex items-center gap-3 border-b border-line px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            <ShieldCheck className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <div className="text-lg font-semibold leading-tight text-ink">Complisoc</div>
            <div className="text-xs text-slate-500">Compliance intelligence</div>
          </div>
          <button
            className="ml-auto lg:hidden icon-button border-0 p-1"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <Nav view={view} onViewChange={(id) => { onViewChange(id); setSidebarOpen(false); }} />
        <div className="mt-auto border-t border-line px-5 py-3 text-xs text-slate-400">
          v0.1 · deterministic mapping
        </div>
      </aside>

      <main className="flex-1 min-w-0 lg:overflow-y-auto">
        <header className="sticky top-0 z-20 border-b border-line bg-white/90 px-4 py-3 backdrop-blur md:px-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <button
                className="lg:hidden icon-button border-0 p-1"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open sidebar"
              >
                <Menu className="h-5 w-5" aria-hidden />
              </button>
              <div>
                <h1 className="text-xl font-semibold text-ink">{active.label}</h1>
                <p className="mt-0.5 text-sm text-slate-500">{active.description}</p>
              </div>
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
          <nav className="mt-3 flex gap-1.5 overflow-x-auto lg:hidden" aria-label="Mobile navigation">
            {navigation.map((item) => (
              <button
                className={`shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 ${
                  view === item.id
                    ? "bg-brand-600 text-white shadow-sm"
                    : "bg-panel text-slate-600 hover:bg-slate-100"
                }`}
                key={item.id}
                onClick={() => onViewChange(item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </header>
        <div className="space-y-5 p-4 md:p-6 overflow-x-hidden">{children}</div>
      </main>
    </div>
  );
}

function Nav({ view, onViewChange }: { view: ViewId; onViewChange: (view: ViewId) => void }) {
  return (
    <nav className="flex-1 space-y-0.5 overflow-y-auto p-3" aria-label="Sidebar">
      {navigation.map((item) => {
        const Icon = item.icon;
        const isActive = view === item.id;
        return (
          <button
            className={`relative flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 ${
              isActive
                ? "bg-brand-50 text-brand-700"
                : "text-slate-600 hover:bg-panel hover:text-slate-900"
            }`}
            key={item.id}
            onClick={() => onViewChange(item.id)}
            aria-current={isActive ? "page" : undefined}
          >
            {isActive ? <span className="absolute inset-y-1.5 left-0 w-1 rounded-full bg-brand-600" aria-hidden /> : null}
            <Icon className="h-4 w-4 flex-shrink-0" aria-hidden />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
