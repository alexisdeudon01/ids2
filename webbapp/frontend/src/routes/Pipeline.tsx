import { useEffect, useState } from "react";
import { Card, Metric, ProgressBar, Text, Title } from "@tremor/react";

type PipelineStatus = {
  interface: string;
  suricata: string;
  vector: string;
  elasticsearch: string;
  timestamp: string;
};

const statusColor = (status: string) => {
  if (status === "running" || status === "green") return "emerald";
  if (status === "stopped") return "rose";
  return "amber";
};

export default function PipelineRoute() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch("/api/pipeline/status");
        if (!response.ok) {
          throw new Error("Impossible de récupérer le statut pipeline");
        }
        setStatus(await response.json());
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      }
    };

    fetchStatus();
  }, []);

  if (error) {
    return (
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Pipeline Status</Title>
        <Text className="mt-2 text-rose-300">{error}</Text>
      </Card>
    );
  }

  if (!status) {
    return (
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Pipeline Status</Title>
        <Text className="mt-2 text-slate-400">Chargement...</Text>
      </Card>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Suricata</Title>
        <Metric>{status.suricata}</Metric>
        <ProgressBar value={status.suricata === "running" ? 100 : 20} color={statusColor(status.suricata)} className="mt-4" />
      </Card>
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Vector</Title>
        <Metric>{status.vector}</Metric>
        <ProgressBar value={status.vector === "running" ? 100 : 20} color={statusColor(status.vector)} className="mt-4" />
      </Card>
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Elasticsearch</Title>
        <Metric>{status.elasticsearch}</Metric>
        <ProgressBar value={status.elasticsearch === "green" ? 100 : 40} color={statusColor(status.elasticsearch)} className="mt-4" />
      </Card>
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Interface</Title>
        <Text className="mt-2 text-slate-400">{status.interface}</Text>
        <Text className="mt-4 text-xs text-slate-500">Last update: {status.timestamp}</Text>
      </Card>
    </div>
  );
}
