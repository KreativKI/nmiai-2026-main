import { useState, useEffect, useCallback } from "react";
import { MetricCard } from "./MetricCard";

const ENDPOINT = "https://tripletex-agent-795548831221.europe-west4.run.app/solve";

// 30 task types from the Tripletex competition spec
const TASK_TYPES = [
  "create_customer", "create_supplier", "create_employee", "create_product",
  "create_department", "create_project", "create_invoice", "create_order",
  "create_voucher", "create_payment", "create_account", "create_bank_reconciliation",
  "update_customer", "update_supplier", "update_employee", "update_product",
  "update_department", "update_project", "update_invoice", "update_order",
  "close_invoice", "approve_voucher", "post_journal", "create_timesheet",
  "create_travel_expense", "create_salary_transaction", "balance_report",
  "profit_loss_report", "vat_report", "general_query",
];

interface EndpointStatus {
  status: "up" | "down" | "checking";
  latencyMs: number | null;
  lastChecked: string | null;
}

export function NLPView() {
  const [endpointStatus, setEndpointStatus] = useState<EndpointStatus>({
    status: "checking",
    latencyMs: null,
    lastChecked: null,
  });

  const checkEndpoint = useCallback(async () => {
    setEndpointStatus((prev) => ({ ...prev, status: "checking" }));
    const start = performance.now();
    try {
      const resp = await fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: "health check", task_type: "ping" }),
        signal: AbortSignal.timeout(10000),
      });
      const latencyMs = Math.round(performance.now() - start);
      setEndpointStatus({
        status: resp.ok || resp.status === 422 ? "up" : "down",
        latencyMs,
        lastChecked: new Date().toLocaleTimeString("en-GB", { hour12: false }),
      });
    } catch {
      setEndpointStatus({
        status: "down",
        latencyMs: null,
        lastChecked: new Date().toLocaleTimeString("en-GB", { hour12: false }),
      });
    }
  }, []);

  useEffect(() => {
    checkEndpoint();
    const interval = setInterval(checkEndpoint, 60000);
    return () => clearInterval(interval);
  }, [checkEndpoint]);

  const statusColor =
    endpointStatus.status === "up"
      ? "text-green-600"
      : endpointStatus.status === "down"
        ? "text-red-600"
        : "text-amber-500";

  const statusDot =
    endpointStatus.status === "up"
      ? "bg-green-400"
      : endpointStatus.status === "down"
        ? "bg-red-400"
        : "bg-amber-400 animate-pulse";

  return (
    <div className="flex-1 flex flex-col overflow-auto p-6 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-sky-800 font-[Fredoka]">
            Tripletex - AI Accounting Agent
          </h2>
          <p className="text-xs text-sky-500">
            30 task types, 3 tiers, 5 submissions/task/day
          </p>
        </div>
        <button
          onClick={checkEndpoint}
          className="px-3 py-1.5 rounded-full bg-white/60 text-xs font-semibold text-sky-600 hover:bg-white/80 transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Status metrics */}
      <div className="flex gap-3">
        <div className="rounded-2xl bg-white/70 backdrop-blur-sm border border-white/40 shadow-lg px-5 py-4 min-w-[180px]">
          <p className="text-xs font-medium text-sky-600 uppercase tracking-wide">Endpoint</p>
          <div className="flex items-center gap-2 mt-1">
            <div className={`w-3 h-3 rounded-full ${statusDot}`} />
            <span className={`text-lg font-bold font-[Fredoka] ${statusColor}`}>
              {endpointStatus.status.toUpperCase()}
            </span>
          </div>
          {endpointStatus.lastChecked && (
            <p className="text-xs text-sky-400 mt-1">
              Checked: {endpointStatus.lastChecked}
            </p>
          )}
        </div>
        <MetricCard
          label="Latency"
          value={endpointStatus.latencyMs != null ? `${endpointStatus.latencyMs}ms` : "-"}
          subtitle="last check"
        />
        <MetricCard label="Task Types" value="30" subtitle="3 tiers" />
        <MetricCard label="Rate Limit" value="5/type/day" subtitle="resets 01:00 CET" />
      </div>

      {/* Task type grid */}
      <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4">
        <h3 className="text-sm font-bold text-sky-700 font-[Fredoka] mb-3">
          Task Types (30 total)
        </h3>
        <div className="grid grid-cols-5 gap-2">
          {TASK_TYPES.map((type) => {
            const tier = type.startsWith("create_") ? 1
              : type.startsWith("update_") || type.startsWith("close_") || type.startsWith("approve_") || type.startsWith("post_") ? 2
              : 3;
            const tierColor = tier === 1 ? "bg-green-100 border-green-300 text-green-800"
              : tier === 2 ? "bg-amber-100 border-amber-300 text-amber-800"
              : "bg-red-100 border-red-300 text-red-800";

            return (
              <div
                key={type}
                className={`rounded-lg border px-3 py-2 ${tierColor}`}
              >
                <p className="text-xs font-semibold truncate">{type.replace(/_/g, " ")}</p>
                <p className="text-[10px] opacity-70">Tier {tier} ({tier}x)</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Endpoint URL */}
      <div className="rounded-2xl bg-white/30 backdrop-blur-sm border border-white/20 p-3">
        <p className="text-xs text-sky-500 font-mono break-all">{ENDPOINT}</p>
      </div>
    </div>
  );
}
