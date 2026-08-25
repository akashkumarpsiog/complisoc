import { ShieldCheck, Menu, X } from "lucide-react";
import { useState } from "react";
import { navigation, type ViewId } from "../navigation";

export function Layout({
  view,
  onViewChange,
  children,
}: {
  view: ViewId;
  onViewChange: (view: ViewId) => void;
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const active = navigation.find((item) => item.id === view) || navigation[0];

  return (
    <div className="flex flex-col lg:h-screen lg:flex-row lg:overflow-hidden">
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-ink/20 backdrop-blur-sm lg:hidden transition-opacity duration-200"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={[
          "fixed inset-y-0 left-0 z-40 w-64 flex-col border-r border-line bg-white transition-transform duration-200 ease-in-out lg:static lg:z-10 lg:translate-x-0 lg:flex lg:h-full",
          sidebarOpen ? "translate-x-0 animate-slide-in-left" : "-translate-x-full",
        ].join(" ")}
      >
        <div className="flex items-center gap-3 border-b border-line px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-500 text-white shadow-sm shadow-brand-500/20">
            <ShieldCheck className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <div className="text-lg font-bold leading-tight text-ink tracking-tight">Complisoc</div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-subtle">Compliance intelligence</div>
          </div>
          <button
            className="ml-auto lg:hidden icon-button !border-0 !p-1 text-subtle hover:text-ink"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <Nav view={view} onViewChange={(id) => { onViewChange(id); setSidebarOpen(false); }} />
        <div className="mt-auto border-t border-line px-5 py-3 text-[11px] font-semibold text-subtle tracking-wide">
          v0.1 · ai mapping
        </div>
      </aside>

      <main className="flex-1 min-w-0 lg:overflow-y-auto">
        <header className="sticky top-0 z-20 border-b border-line bg-white/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-white/80 md:px-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <button
                className="lg:hidden icon-button !border-0 !p-1 text-subtle hover:text-ink"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open sidebar"
              >
                <Menu className="h-5 w-5" aria-hidden />
              </button>
              <div>
                <h1 className="text-xl font-bold text-ink tracking-tight">{active.label}</h1>
                <p className="mt-0.5 text-sm text-muted">{active.description}</p>
              </div>
            </div>
          </div>
          <nav className="mt-3 flex gap-1.5 overflow-x-auto lg:hidden" aria-label="Mobile navigation">
            {navigation.map((item) => (
              <button
                className={`shrink-0 rounded-lg px-3 py-2 text-sm font-semibold transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 ${
                  view === item.id
                    ? "bg-brand-500 text-white shadow-sm shadow-brand-500/20"
                    : "bg-panel text-muted hover:bg-panel-hover hover:text-ink"
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
            className={`relative flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 ${
              isActive
                ? "bg-brand-50 text-brand-700 font-semibold"
                : "text-muted hover:bg-panel-hover hover:text-ink"
            }`}
            key={item.id}
            onClick={() => onViewChange(item.id)}
            aria-current={isActive ? "page" : undefined}
          >
            {isActive ? (
              <span className="absolute inset-y-1.5 left-0 w-1 rounded-full bg-brand-500 shadow-sm shadow-brand-500/30 transition-all duration-200" aria-hidden />
            ) : null}
            <Icon className={`h-4 w-4 flex-shrink-0 transition-colors duration-150 ${isActive ? "text-brand-600" : "text-subtle"}`} aria-hidden />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
