import { NavLink, Route, Routes } from "react-router-dom";

import Dashboard from "./routes/Dashboard";
import SystemRoute from "./routes/System";
import DatabaseRoute from "./routes/Database";
import AlertsRoute from "./routes/Alerts";
import NetworkRoute from "./routes/Network";
import PipelineRoute from "./routes/Pipeline";
import CostsRoute from "./routes/Costs";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/system", label: "System" },
  { to: "/database", label: "Database" },
  { to: "/alerts", label: "Alerts" },
  { to: "/network", label: "Network" },
  { to: "/pipeline", label: "Pipeline" },
  { to: "/costs", label: "Costs" },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-4 py-2 text-sm transition ${
    isActive ? "bg-cyan-500 text-slate-900" : "bg-slate-900/60 text-slate-200 hover:bg-slate-800"
  }`;

export default function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 px-6 py-10 text-slate-100">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm text-slate-400">IDS2 Webbapp</p>
            <h1 className="text-3xl font-semibold">Real-time Security Console</h1>
          </div>
          <nav className="flex flex-wrap gap-2">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={linkClass} end={item.to === "/"}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/system" element={<SystemRoute />} />
          <Route path="/database" element={<DatabaseRoute />} />
          <Route path="/alerts" element={<AlertsRoute />} />
          <Route path="/network" element={<NetworkRoute />} />
          <Route path="/pipeline" element={<PipelineRoute />} />
          <Route path="/costs" element={<CostsRoute />} />
        </Routes>
      </div>
    </div>
  );
}
