import { BarChart3, ClipboardCheck, PanelLeft, Route } from "lucide-react";
import { NavLink, Route as RouterRoute, Routes } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import Evaluations from "./pages/Evaluations";
import Traces from "./pages/Traces";

const navigation = [
  { label: "Dashboard", icon: BarChart3, to: "/" },
  { label: "Traces", icon: Route, to: "/traces" },
  { label: "Evaluations", icon: ClipboardCheck, to: "/evaluations" },
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
          {navigation.map(({ label, icon: Icon, to }) => (
            <NavLink
              className={({ isActive }) =>
                `flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition hover:bg-slate-800 hover:text-white ${
                  isActive ? "bg-slate-800 text-white" : "text-slate-300"
                }`
              }
              key={label}
              to={to}
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="flex flex-1 items-center justify-center p-8">
        <Routes>
          <RouterRoute element={<Dashboard />} path="/" />
          <RouterRoute element={<Traces />} path="/traces" />
          <RouterRoute element={<Evaluations />} path="/evaluations" />
        </Routes>
      </main>
    </div>
  );
}
