import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Activity, Cpu, ShieldAlert, TerminalSquare } from "lucide-react";
import { Card, Metric, ProgressBar, Text, Title } from "@tremor/react";

import { Button } from "@/components/ui/button";

type SystemHealth = {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  temperature?: number | null;
};

export default function App() {
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [dbStatus, setDbStatus] = useState<string>("unknown");

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await fetch("/api/system/health");
        if (response.ok) {
          setSystemHealth(await response.json());
        }
      } catch {
        setSystemHealth(null);
      }
    };

    const fetchDb = async () => {
      try {
        const response = await fetch("/api/db/health");
        if (response.ok) {
          const data = await response.json();
          setDbStatus(data.status ?? "unknown");
        }
      } catch {
        setDbStatus("unknown");
      }
    };

    fetchHealth();
    fetchDb();
  }, []);

  const stats = useMemo(
    () => [
      {
        label: "Inbound Mirror Traffic",
        value: "128 Mbps",
        delta: 68,
        icon: Activity,
      },
      {
        label: "Pi CPU Load",
        value: systemHealth ? `${Math.round(systemHealth.cpu_percent)}%` : "n/a",
        delta: systemHealth ? Math.round(systemHealth.cpu_percent) : 0,
        icon: Cpu,
      },
      {
        label: "Critical Alerts",
        value: "3",
        delta: 30,
        icon: ShieldAlert,
      },
    ],
    [systemHealth],
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 px-8 py-10 text-slate-100">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <Text className="text-slate-400">IDS Orchestrator</Text>
            <Title className="text-3xl">Security Pipeline Command Center</Title>
          </div>
          <Button variant="secondary">Open Pipeline Manager</Button>
        </header>

        <div className="grid gap-6 md:grid-cols-3">
          {stats.map((stat) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <Card className="border border-white/10 bg-glass backdrop-blur">
                <div className="flex items-center justify-between">
                  <div>
                    <Text className="text-slate-400">{stat.label}</Text>
                    <Metric>{stat.value}</Metric>
                  </div>
                  <stat.icon className="h-6 w-6 text-cyan-300" />
                </div>
                <ProgressBar value={stat.delta} color="cyan" className="mt-4" />
              </Card>
            </motion.div>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <Card className="border border-white/10 bg-glass backdrop-blur">
            <div className="flex items-center gap-3">
              <TerminalSquare className="h-5 w-5 text-fuchsia-300" />
              <Title>Live Console</Title>
            </div>
            <div className="mt-4 rounded-lg bg-slate-950/70 p-4 font-mono text-sm text-emerald-200">
              <p>[OK] Suricata running in promiscuous mode on eth0</p>
              <p>[ALERT] Severity 1: ET SCAN Suspicious inbound</p>
              <p>[AI FIX] sudo ip link set eth0 promisc on</p>
            </div>
          </Card>

          <Card className="border border-white/10 bg-glass backdrop-blur">
            <Title>Pipeline Health</Title>
            <Text className="mt-2 text-slate-400">
              Elasticsearch shards • DB: {dbStatus}
            </Text>
            <ProgressBar value={82} color="emerald" className="mt-2" />
            <Text className="mt-6 text-slate-400">Suricata rules sync</Text>
            <ProgressBar value={58} color="amber" className="mt-2" />
            <Button className="mt-6 w-full" variant="ghost">
              Apply Healing Patch
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}
