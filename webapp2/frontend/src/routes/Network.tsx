import { useState } from "react";
import { Card, Metric, Text, Title } from "@tremor/react";
import { Button } from "@/components/ui/button";

type NetworkStats = {
  interface: string;
  bytes_sent: number;
  bytes_recv: number;
  packets_sent: number;
  packets_recv: number;
  bitrate_sent: number;
  bitrate_recv: number;
  timestamp: string;
};

export default function NetworkRoute() {
  const [iface, setIface] = useState("eth0");
  const [stats, setStats] = useState<NetworkStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      const response = await fetch(`/api/network/stats?interface=${encodeURIComponent(iface)}`);
      if (!response.ok) {
        throw new Error("Impossible de récupérer les stats réseau");
      }
      setStats(await response.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
      setStats(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Network Interface</Title>
        <Text className="mt-2 text-slate-400">Choisissez l'interface à inspecter.</Text>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <input
            className="rounded-md border border-white/10 bg-slate-950/60 p-2 text-sm text-slate-100"
            value={iface}
            onChange={(event) => setIface(event.target.value)}
          />
          <Button onClick={fetchStats}>Load Stats</Button>
        </div>
        {error && <Text className="mt-4 text-rose-300">{error}</Text>}
      </Card>

      {stats && (
        <div className="grid gap-6 md:grid-cols-2">
          <Card className="border border-white/10 bg-glass backdrop-blur">
            <Title>Traffic (Mbps)</Title>
            <Metric>{stats.bitrate_recv.toFixed(2)} ↓</Metric>
            <Text className="text-slate-400">{stats.bitrate_sent.toFixed(2)} ↑</Text>
          </Card>
          <Card className="border border-white/10 bg-glass backdrop-blur">
            <Title>Packets</Title>
            <Metric>{stats.packets_recv}</Metric>
            <Text className="text-slate-400">Sent: {stats.packets_sent}</Text>
          </Card>
          <Card className="border border-white/10 bg-glass backdrop-blur">
            <Title>Bytes Received</Title>
            <Metric>{stats.bytes_recv}</Metric>
            <Text className="text-slate-400">Bytes Sent: {stats.bytes_sent}</Text>
          </Card>
          <Card className="border border-white/10 bg-glass backdrop-blur">
            <Title>Timestamp</Title>
            <Text className="mt-2 text-slate-400">{stats.timestamp}</Text>
          </Card>
        </div>
      )}
    </div>
  );
}
