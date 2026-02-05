import { useEffect, useState } from "react";
import { Card, Text, Title } from "@tremor/react";
import { Button } from "@/components/ui/button";

type Alert = {
  timestamp: string;
  severity: number;
  signature: string;
  src_ip?: string | null;
  dest_ip?: string | null;
};

export default function AlertsRoute() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [signature, setSignature] = useState("Test Alert");
  const [severity, setSeverity] = useState(1);
  const [srcIp, setSrcIp] = useState("192.168.1.100");

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/alerts/recent?limit=50");
      if (!response.ok) {
        throw new Error("Impossible de récupérer les alertes");
      }
      setAlerts(await response.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  const handleAddAlert = async () => {
    const params = new URLSearchParams({
      severity: String(severity),
      signature,
      src_ip: srcIp,
    });
    await fetch(`/api/alerts/add?${params.toString()}`, { method: "POST" });
    await fetchAlerts();
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Recent Alerts</Title>
        {loading ? (
          <Text className="mt-2 text-slate-400">Chargement...</Text>
        ) : error ? (
          <Text className="mt-2 text-rose-300">{error}</Text>
        ) : alerts.length === 0 ? (
          <Text className="mt-2 text-slate-400">Aucune alerte disponible.</Text>
        ) : (
          <ul className="mt-4 space-y-3 text-sm text-slate-200">
            {alerts.map((alert, index) => (
              <li key={`${alert.timestamp}-${index}`} className="rounded-md bg-slate-900/60 p-3">
                <div className="flex items-center justify-between">
                  <Text className="text-slate-300">{alert.signature}</Text>
                  <Text className="text-emerald-300">Severity {alert.severity}</Text>
                </div>
                <Text className="text-xs text-slate-500">{alert.timestamp}</Text>
                <Text className="text-xs text-slate-500">{alert.src_ip ?? "n/a"} → {alert.dest_ip ?? "n/a"}</Text>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="border border-white/10 bg-glass backdrop-blur">
        <Title>Inject Test Alert</Title>
        <label className="mt-4 block text-sm text-slate-400">Signature</label>
        <input
          className="mt-1 w-full rounded-md border border-white/10 bg-slate-950/60 p-2 text-sm text-slate-100"
          value={signature}
          onChange={(event) => setSignature(event.target.value)}
        />
        <label className="mt-4 block text-sm text-slate-400">Severity</label>
        <input
          type="number"
          className="mt-1 w-full rounded-md border border-white/10 bg-slate-950/60 p-2 text-sm text-slate-100"
          value={severity}
          onChange={(event) => setSeverity(Number(event.target.value))}
          min={1}
          max={10}
        />
        <label className="mt-4 block text-sm text-slate-400">Source IP</label>
        <input
          className="mt-1 w-full rounded-md border border-white/10 bg-slate-950/60 p-2 text-sm text-slate-100"
          value={srcIp}
          onChange={(event) => setSrcIp(event.target.value)}
        />
        <Button className="mt-6 w-full" onClick={handleAddAlert}>
          Add Alert
        </Button>
      </Card>
    </div>
  );
}
