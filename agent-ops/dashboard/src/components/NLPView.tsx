import { useState, useEffect, useCallback } from "react";
import { MetricCard } from "./MetricCard";
import { NLPSubmissionFeed } from "./NLPSubmissionFeed";

const ENDPOINT_URL = "https://tripletex-agent-795548831221.europe-west4.run.app/solve";
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

interface TaskScore {
  task_type: string;
  best_checks: number;
  total_checks: number;
  best_percentage: number;
  attempts: number;
}

interface EndpointStatus {
  status: "up" | "down" | "checking";
  latencyMs: number | null;
  lastChecked: string | null;
}

function taskScoreColor(isPerfect: boolean, hasPartial: boolean): string {
  if (isPerfect) return "text-green-700";
  if (hasPartial) return "text-amber-700";
  return "text-red-600";
}

function taskBarColor(isPerfect: boolean, hasPartial: boolean): string {
  if (isPerfect) return "bg-green-500";
  if (hasPartial) return "bg-amber-500";
  return "bg-red-400";
}

export function NLPView() {
  const [endpointStatus, setEndpointStatus] = useState<EndpointStatus>({
    status: "checking", latencyMs: null, lastChecked: null,
  });
  const [taskScores, setTaskScores] = useState<Map<string, TaskScore>>(new Map());
  const [totalScore, setTotalScore] = useState<number | null>(null);
  const [tasksSolved, setTasksSolved] = useState<string | null>(null);

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

  // Load per-task scores from nlp_task_scores.json (scraped from competition page)
  useEffect(() => {
    const load = () => {
      fetch("/data/nlp_task_scores.json", { cache: "no-store" })
        .then((r) => r.ok ? r.json() : null)
        .then((d: { tasks?: TaskScore[]; total_score?: number; tasks_solved?: string } | null) => {
          if (d?.tasks) {
            const m = new Map<string, TaskScore>();
            for (const t of d.tasks) m.set(t.task_type, t);
            setTaskScores(m);
          }
          if (d?.total_score != null) setTotalScore(d.total_score);
          if (d?.tasks_solved) setTasksSolved(d.tasks_solved);
        })
        .catch(() => { /* no per-task data yet */ });
    };
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    checkEndpoint();
    const interval = setInterval(checkEndpoint, 60000);
    return () => clearInterval(interval);
  }, [checkEndpoint]);

  const STATUS_STYLES: Record<EndpointStatus["status"], { dot: string; text: string }> = {
    up: { dot: "bg-green-400", text: "text-green-600" },
    down: { dot: "bg-red-400", text: "text-red-600" },
    checking: { dot: "bg-amber-400 animate-pulse", text: "text-amber-500" },
  };
  const { dot: statusDot, text: statusColor } = STATUS_STYLES[endpointStatus.status];

  // Count scored tasks
  const scoredCount = taskScores.size;
  const perfectCount = Array.from(taskScores.values()).filter((t) => t.best_percentage === 100).length;

  return (
    <div className="flex-1 flex flex-col overflow-auto p-6 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-sky-800 font-[Fredoka]">
            Tripletex - AI Accounting Agent
          </h2>
          <p className="text-xs text-sky-500">
            30 task types, 3 tiers, 10 submissions/task/day
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
        <MetricCard
          label="Total Score"
          value={totalScore != null ? totalScore.toFixed(1) : "-"}
          subtitle="sum of best per task"
        />
        <MetricCard
          label="Tasks Scored"
          value={tasksSolved ?? `${scoredCount}/30`}
          subtitle={`${perfectCount} perfect`}
        />
        <MetricCard
          label="Perfect"
          value={perfectCount}
          subtitle="100% score"
          color={perfectCount > 0 ? "text-green-600" : "text-sky-600"}
        />
      </div>

      {/* Task type grid with live scores */}
      <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4">
        <h3 className="text-sm font-bold text-sky-700 font-[Fredoka] mb-3">
          Task Types - 30 tasks across 3 tiers
        </h3>
        <div className="grid grid-cols-5 gap-2">
          {TASK_TYPES.map(({ name, tier }) => {
            const score = taskScores.get(name);
            const hasData = score != null;
            const isPerfect = score?.best_percentage === 100;
            const hasPartial = hasData && !isPerfect && score.best_percentage > 0;

            // Colors: grey/dull for untried, colored for attempted, gold star for perfect
            let cardStyle = "border-slate-200 bg-slate-100/40 text-slate-400 opacity-50";
            if (isPerfect) {
              cardStyle = "border-green-400 bg-green-50 text-green-800 shadow-md ring-1 ring-green-300";
            } else if (hasPartial) {
              cardStyle = "border-amber-300 bg-amber-50/80 text-amber-800";
            } else if (hasData) {
              cardStyle = "border-red-300 bg-red-50/80 text-red-800";
            }

            return (
              <div
                key={name}
                className={`rounded-lg border px-3 py-2 text-left transition-all ${cardStyle}`}
              >
                <div className="flex items-center gap-1">
                  {isPerfect && <span className="text-sm" title="Perfect score!">&#9733;</span>}
                  <p className="text-xs font-semibold truncate flex-1">
                    {name.replace(/_/g, " ")}
                  </p>
                </div>
                <div className="flex items-center justify-between mt-1">
                  <p className="text-[10px] opacity-60">
                    T{tier} ({tier}x)
                  </p>
                  {hasData ? (
                    <p className={`text-[10px] font-bold ${
                      taskScoreColor(isPerfect, hasPartial)
                    }`}>
                      {score.best_checks}/{score.total_checks}
                      {score.attempts > 1 && (
                        <span className="text-[9px] opacity-60 ml-0.5">
                          ({score.attempts}x)
                        </span>
                      )}
                    </p>
                  ) : (
                    <p className="text-[10px] text-slate-300">--</p>
                  )}
                </div>
                {/* Score bar */}
                {hasData && (
                  <div className="mt-1 h-1 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${taskBarColor(isPerfect, hasPartial)}`}
                      style={{ width: `${score.best_percentage}%` }}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Live Submission Feed */}
      <NLPSubmissionFeed />

      {/* Endpoint URL */}
      <div className="rounded-2xl bg-white/30 backdrop-blur-sm border border-white/20 p-3">
        <p className="text-xs text-sky-500 font-mono break-all">{ENDPOINT_URL}</p>
      </div>
    </div>
  );
}
