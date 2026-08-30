import { useState } from "react";
import { DagExplorer } from "./components/graph/DagExplorer";
import { RegistryUploader } from "./components/graph/RegistryUploader";
import { QueryConsole } from "./components/query/QueryConsole";
import { RolesPanel } from "./components/admin/RolesPanel";

type Tab = "query" | "dag" | "registry" | "admin";

export default function App() {
  const [tab, setTab] = useState<Tab>("query");

  return (
    <div className="app-shell">
      <header>
        <h1>Semantic Layer Shell</h1>
        <p>Intelligence Hub pilot — deterministic SQL assembly from graph-defined metadata.</p>
      </header>
      <nav className="tabs">
        <button className={tab === "query" ? "active" : ""} onClick={() => setTab("query")}>
          Query Console
        </button>
        <button className={tab === "dag" ? "active" : ""} onClick={() => setTab("dag")}>
          DAG Explorer
        </button>
        <button className={tab === "registry" ? "active" : ""} onClick={() => setTab("registry")}>
          Registry
        </button>
        <button className={tab === "admin" ? "active" : ""} onClick={() => setTab("admin")}>
          Admin
        </button>
      </nav>
      {tab === "query" && <QueryConsole />}
      {tab === "dag" && <DagExplorer />}
      {tab === "registry" && <RegistryUploader />}
      {tab === "admin" && <RolesPanel />}
    </div>
  );
}
