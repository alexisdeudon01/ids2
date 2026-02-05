import { useEffect, useState } from "react";
import { Card, Text, Title } from "@tremor/react";

export default function DatabaseRoute() {
  const [status, setStatus] = useState<string>("unknown");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch("/api/db/health");
        if (!response.ok) {
          throw new Error("Impossible de contacter la base");
        }
        const data = await response.json();
        setStatus(data.status ?? "unknown");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      }
    };

    fetchStatus();
  }, []);

  return (
    <Card className="border border-white/10 bg-glass backdrop-blur">
      <Title>Database Health</Title>
      {error ? (
        <Text className="mt-2 text-rose-300">{error}</Text>
      ) : (
        <Text className="mt-2 text-slate-400">Status: {status}</Text>
      )}
      <Text className="mt-4 text-slate-500">Base SQLite locale utilisée par l'API.</Text>
    </Card>
  );
}
