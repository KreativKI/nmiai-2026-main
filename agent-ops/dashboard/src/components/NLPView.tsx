import { useState, useEffect, useCallback } from "react";
import { MetricCard } from "./MetricCard";

const ENDPOINT_DISPLAY = "https://tripletex-agent-795548831221.europe-west4.run.app/solve";
const ENDPOINT_PROXY = "/api/nlp-health";

const TASK_TYPES: { name: string; tier: number }[] = [
  // Tier 1
  { name: "create_customer", tier: 1 }, { name: "create_supplier", tier: 1 },
  { name: "create_employee", tier: 1 }, { name: "create_product", tier: 1 },
  { name: "create_department", tier: 1 }, { name: "create_project", tier: 1 },
  { name: "create_invoice", tier: 1 }, { name: "create_order", tier: 1 },
  { name: "create_voucher", tier: 1 }, { name: "create_payment", tier: 1 },
  { name: "create_account", tier: 1 }, { name: "create_bank_reconciliation", tier: 1 },
  // Tier 2
  { name: "update_customer", tier: 2 }, { name: "update_supplier", tier: 2 },
  { name: "update_employee", tier: 2 }, { name: "update_product", tier: 2 },
  { name: "update_department", tier: 2 }, { name: "update_project", tier: 2 },
  { name: "update_invoice", tier: 2 }, { name: "update_order", tier: 2 },
  { name: "close_invoice", tier: 2 }, { name: "approve_voucher", tier: 2 },
  // Tier 3
  { name: "post_journal", tier: 3 }, { name: "create_timesheet", tier: 3 },
  { name: "create_travel_expense", tier: 3 }, { name: "create_salary_transaction", tier: 3 },
  { name: "balance_report", tier: 3 }, { name: "profit_loss_report", tier: 3 },
  { name: "vat_report", tier: 3 }, { name: "general_query", tier: 3 },
];

interface TaskLog {
  timestamp: string;
  status: string;
  api_calls: number;
  errors_4xx: number;
  elapsed_s: number;
  summary?: string;
}

interface EndpointStatus {
  status: "up" | "down" | "checking";
  latencyMs: number | null;
  lastChecked: string | null;
}

export function NLPView() {
  const [endpointStatus, setEndpointStatus] = useState<EndpointStatus>({
    status: "checking", latencyMs: null, lastChecked: null,
  });
  const [taskLogs, setTaskLogs] = useState<TaskLog[]>([]);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);

  const checkEndpoint = useCallback(async () => {
    setEndpointStatus((prev) => ({ ...prev, status: "checking" }));
    const start = performance.now();
    try {
      const resp = await fetch(ENDPOINT_PROXY, {
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
        status: "down", latencyMs: null,
        lastChecked: new Date().toLocaleTimeString("en-GB", { hour12: false }),
      });
    }
  }, []);

  // Load task logs
  useEffect(() => {
    fetch("/data/nlp_task_log.json")
      .then((r) => r.ok ? r.json() : [])
      .then((d) => setTaskLogs(d as TaskLog[]))
      .catch(() => setTaskLogs([]));
  }, []);

  useEffect(() => {
    checkEndpoint();
    const interval = setInterval(checkEndpoint, 60000);
    return () => clearInterval(interval);
  }, [checkEndpoint]);

  const statusDot = endpointStatus.status === "up" ? "bg-green-400"
    : endpointStatus.status === "down" ? "bg-red-400"
    : "bg-amber-400 animate-pulse";

  const statusColor = endpointStatus.status === "up" ? "text-green-600"
    : endpointStatus.status === "down" ? "text-red-600"
    : "text-amber-500";

  // Stats
  const completedTasks = taskLogs.filter((t) => t.status === "completed").length;
  const totalAPICalls = taskLogs.reduce((s, t) => s + (t.api_calls || 0), 0);
  const totalErrors = taskLogs.reduce((s, t) => s + (t.errors_4xx || 0), 0);
  const avgElapsed = taskLogs.length > 0
    ? (taskLogs.reduce((s, t) => s + (t.elapsed_s || 0), 0) / taskLogs.length).toFixed(1)
    : "-";


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

      {/* Status + metrics */}
      <div className="flex gap-3 flex-wrap">
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
              {endpointStatus.latencyMs != null ? `${endpointStatus.latencyMs}ms` : ""} at {endpointStatus.lastChecked}
            </p>
          )}
        </div>
        <MetricCard label="Tasks Run" value={completedTasks} subtitle={`${totalAPICalls} API calls`} />
        <MetricCard label="4xx Errors" value={totalErrors} color={totalErrors > 0 ? "text-red-600" : "text-green-700"} />
        <MetricCard label="Avg Time" value={`${avgElapsed}s`} subtitle="per task" />
      </div>

      {/* Task type grid - clickable */}
      <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4">
        <h3 className="text-sm font-bold text-sky-700 font-[Fredoka] mb-3">
          Task Types - Click for details
        </h3>
        <div className="grid grid-cols-5 gap-2">
          {TASK_TYPES.map(({ name, tier }) => {
            const isSelected = selectedTask === name;
            const tierColor = tier === 1 ? "border-green-300 text-green-800"
              : tier === 2 ? "border-amber-300 text-amber-800"
              : "border-red-300 text-red-800";
            const tierBg = tier === 1 ? "bg-green-50" : tier === 2 ? "bg-amber-50" : "bg-red-50";

            return (
              <button
                key={name}
                onClick={() => setSelectedTask(isSelected ? null : name)}
                className={`rounded-lg border px-3 py-2 text-left transition-all hover:shadow-md ${tierColor} ${
                  isSelected ? "ring-2 ring-sky-500 shadow-lg " + tierBg : tierBg + "/60"
                }`}
              >
                <p className="text-xs font-semibold truncate">{name.replace(/_/g, " ")}</p>
                <p className="text-[10px] opacity-60">Tier {tier} ({tier}x)</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Selected task detail / Execution log */}
      {selectedTask && (
        <div className="rounded-2xl bg-white/60 backdrop-blur-sm border border-white/30 p-4">
          <h3 className="text-sm font-bold text-sky-700 font-[Fredoka] mb-2">
            {selectedTask.replace(/_/g, " ")}
          </h3>
          <p className="text-xs text-sky-500 mb-3">
            Click Submit on app.ainm.no to test this task type. Results appear after the competition evaluates your endpoint.
          </p>
          <p className="text-xs text-sky-400">
            Task-specific scores are only visible on the competition leaderboard.
            The logs below show all endpoint calls (not filtered by task type since the competition assigns tasks randomly).
          </p>
        </div>
      )}

      {/* Execution log */}
      <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4">
        <h3 className="text-sm font-bold text-sky-700 font-[Fredoka] mb-3">
          Recent Executions ({taskLogs.length})
        </h3>
        {taskLogs.length === 0 ? (
          <div className="text-xs text-sky-400">
            No task logs yet. Run: <code className="bg-white/60 px-1 rounded">python3 tools/fetch_nlp_logs.py</code>
          </div>
        ) : (
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {[...taskLogs].reverse().map((task, i) => (
              <div key={i} className="flex items-start gap-3 text-xs border-b border-sky-100/30 pb-2">
                <div className={`w-2 h-2 rounded-full mt-1 flex-shrink-0 ${
                  task.status === "completed" ? "bg-green-400" : "bg-red-400"
                }`} />
                <div className="flex-1 min-w-0">
                  {task.summary && (
                    <p className="text-sky-700 truncate">{task.summary.split("\t")[0]}</p>
                  )}
                  <p className="text-sky-400">
                    {task.api_calls} calls, {task.errors_4xx} errors, {task.elapsed_s}s
                    <span className="ml-2 text-sky-300">{task.timestamp}</span>
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Endpoint URL */}
      <div className="rounded-2xl bg-white/30 backdrop-blur-sm border border-white/20 p-3">
        <p className="text-xs text-sky-500 font-mono break-all">{ENDPOINT_DISPLAY}</p>
      </div>
    </div>
  );
}
