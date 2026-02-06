import { useEffect, useState } from "react";
import { Card, Text, Title } from "@tremor/react";

type InstanceCost = {
  id?: string;
  region?: string;
  state?: string;
  instance_type?: string;
  public_ip?: string;
  ec2_hourly_usd?: number;
  ec2_monthly_usd?: number;
  elastic_hourly_usd?: number;
  elastic_monthly_usd?: number;
  total_hourly_usd?: number;
  total_monthly_usd?: number;
};

type CostsResponse = {
  instances: InstanceCost[];
  total_hourly_usd?: number;
  total_monthly_usd?: number;
  error?: string;
};

export default function Costs() {
  const [data, setData] = useState<CostsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetch("/api/aws/costs")
      .then((res) => res.json())
      .then((payload: CostsResponse) => {
        if (active) {
          setData(payload);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setData({ instances: [], error: "Failed to load costs." });
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="grid gap-6">
      <div>
        <Title>AWS Costs</Title>
        <Text className="text-slate-400">
          Estimated EC2 + Elastic (Docker) costs for ELK instances.
        </Text>
      </div>

      {loading ? (
        <Card className="border border-white/10 bg-glass backdrop-blur">
          <Text>Loading...</Text>
        </Card>
      ) : data?.error ? (
        <Card className="border border-red-500/40 bg-red-950/30">
          <Text>{data.error}</Text>
        </Card>
      ) : (
        <>
          <Card className="border border-white/10 bg-glass backdrop-blur">
            <div className="flex flex-wrap items-center gap-6">
              <div>
                <Text>Total hourly</Text>
                <Title>${data?.total_hourly_usd?.toFixed(4) ?? "0.0000"}</Title>
              </div>
              <div>
                <Text>Total monthly (est.)</Text>
                <Title>${data?.total_monthly_usd?.toFixed(2) ?? "0.00"}</Title>
              </div>
            </div>
          </Card>

          <div className="grid gap-4">
            {data?.instances?.length ? (
              data.instances.map((inst) => (
                <Card key={`${inst.region}-${inst.id}`} className="border border-white/10 bg-glass backdrop-blur">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <Title className="text-lg">{inst.id}</Title>
                      <Text className="text-slate-400">
                        {inst.region} • {inst.instance_type} • {inst.state}
                      </Text>
                      <Text className="text-slate-400">Public IP: {inst.public_ip ?? "n/a"}</Text>
                    </div>
                    <div className="text-right">
                      <Text>EC2 hourly</Text>
                      <Title className="text-lg">${(inst.ec2_hourly_usd ?? 0).toFixed(4)}</Title>
                      <Text className="mt-2 text-slate-400">
                        Monthly: ${(inst.ec2_monthly_usd ?? 0).toFixed(2)}
                      </Text>
                    </div>
                  </div>
                </Card>
              ))
            ) : (
              <Card className="border border-white/10 bg-glass backdrop-blur">
                <Text>No ELK instances found.</Text>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
}
