import { BarChart3, ClipboardCheck, PanelLeft, Route } from "lucide-react";

const navigation = [
  { label: "Dashboard", icon: BarChart3 },
  { label: "Traces", icon: Route },
  { label: "Evaluations", icon: ClipboardCheck },
];

export default function App() {
  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <aside className="flex w-64 flex-col border-r border-slate-800 bg-slate-900/70 p-4">
        <div className="mb-10 flex items-center gap-3 px-2 text-sm font-semibold tracking-wide">
          <PanelLeft className="h-5 w-5 text-cyan-400" />
          <span>RAG Eval Harness</span>
        </div>
        <nav aria-label="Primary navigation" className="space-y-1">
          {navigation.map(({ label, icon: Icon }) => (
            <button
              className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-slate-300 transition hover:bg-slate-800 hover:text-white"
              key={label}
              type="button"
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="flex flex-1 items-center justify-center p-8">
        <p className="text-sm text-slate-500">Phase 0 dashboard shell</p>
      </main>
    </div>
  );
}
