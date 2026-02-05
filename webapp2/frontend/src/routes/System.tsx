import { useEffect, useState } from "react";
import { Card, Metric, ProgressBar, Text, Title } from "@tremor/react";

const barColor = (value: number) => {
  if (value >= 85) return "rose";
  if (value >= 70) return "amber";
  return "emerald";
};

type SystemHealth = {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  temperature?: number | null;
};

export default function SystemRoute() {
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await fetch("/api/system/health");
        if (!response.ok) {
          throw new Error("Impossible de récupérer les métriques");
        }
        setSystemHealth(await response.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      }
    };

    fetchHealth();
  }, []);

  if (error) {
    return (
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>System Health</Title>
        <Text className="mt-2 text-rose-300">{error}</Text>
      </Card>
    );
  }

  if (!systemHealth) {
    return (
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>System Health</Title>
        <Text className="mt-2 text-slate-400">Chargement...</Text>
      </Card>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>CPU Usage</Title>
        <Metric>{Math.round(systemHealth.cpu_percent)}%</Metric>
        <ProgressBar
          value={systemHealth.cpu_percent}
          color={barColor(systemHealth.cpu_percent)}
          className="mt-4"
        />
      </Card>

      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Memory Usage</Title>
        <Metric>{Math.round(systemHealth.memory_percent)}%</Metric>
        <ProgressBar
          value={systemHealth.memory_percent}
          color={barColor(systemHealth.memory_percent)}
          className="mt-4"
        />
      </Card>

      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Disk Usage</Title>
        <Metric>{Math.round(systemHealth.disk_percent)}%</Metric>
        <ProgressBar
          value={systemHealth.disk_percent}
          color={barColor(systemHealth.disk_percent)}
          className="mt-4"
        />
      </Card>

      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Temperature</Title>
        <Metric>{systemHealth.temperature ? `${systemHealth.temperature.toFixed(1)} °C` : "n/a"}</Metric>
        <Text className="mt-2 text-slate-400">Thermal zone 0</Text>
      </Card>
    </div>
  );
}
