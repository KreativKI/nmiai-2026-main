import { useState, useEffect, useCallback } from "react";

interface Submission {
  timestamp: string;
  attempt: number;
  success: boolean;
  checks_passed: number | null;
  total_checks: number | null;
  percentage: number | null;
  daily_used: number | null;
  daily_limit: number | null;
  error: string | null;
  score?: number | null;
  task_type?: string | null;
}

function utcToCET(isoString: string): string {
  const d = new Date(isoString);
  // CET = UTC+1 (Norway until March 29)
  const cetMs = d.getTime() + 1 * 60 * 60 * 1000;
  const cet = new Date(cetMs);
  const hh = String(cet.getUTCHours()).padStart(2, "0");
  const mm = String(cet.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

function scoreBarColor(percentage: number): string {
  if (percentage >= 75) return "#22c55e";
  if (percentage >= 25) return "#f59e0b";
  return "#ef4444";
}

function budgetBarColor(usagePercent: number): string {
  if (usagePercent > 80) return "#ef4444";
  if (usagePercent > 50) return "#f59e0b";
  return "#22c55e";
}

function successRateColor(rate: number): string {
  if (rate >= 75) return "text-green-600";
  if (rate >= 50) return "text-amber-600";
  return "text-red-600";
}

export function NLPSubmissionFeed() {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const resp = await fetch("/data/nlp_submissions.json");
      if (!resp.ok) {
        setSubmissions([]);
        return;
      }
      const data: Submission[] = await resp.json();
      setSubmissions(data);
    } catch {
      setSubmissions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Compute stats
  const totalSubmissions = submissions.length;
  const successfulSubs = submissions.filter((s) => s.success);
  const successRate =
    totalSubmissions > 0
      ? Math.round((successfulSubs.length / totalSubmissions) * 100)
      : 0;

  // Perfect scores: success + percentage === 100
  const perfectCount = submissions.filter(
    (s) => s.success && s.percentage === 100
  ).length;

  // Average score: only from entries that have a numeric percentage
  const scored = submissions.filter((s) => s.percentage != null);
  const avgScore =
    scored.length > 0
      ? Math.round(
          scored.reduce((sum, s) => sum + (s.percentage ?? 0), 0) /
            scored.length
        )
      : 0;

  // Daily budget: use latest entry with daily_used/daily_limit
  const latestWithBudget = [...submissions]
    .reverse()
    .find((s) => s.daily_used != null && s.daily_limit != null);
  const hasBudgetData = latestWithBudget != null;
  const dailyUsed = latestWithBudget?.daily_used ?? 0;
  const dailyLimit = latestWithBudget?.daily_limit ?? 180;
  const budgetPct = dailyLimit > 0 ? (dailyUsed / dailyLimit) * 100 : 0;

  // Show last 20 entries, newest first
  const recentSubs = [...submissions].reverse().slice(0, 20);

  if (loading) {
    return (
      <div className="rounded-2xl bg-white/60 backdrop-blur-sm border border-white/40 shadow-lg p-5">
        <p className="text-xs text-sky-400 animate-pulse">
          Loading NLP submissions...
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl bg-white/60 backdrop-blur-sm border border-white/40 shadow-lg p-5">
      {/* Header */}
      <h3 className="text-sm font-bold text-sky-800 font-[Fredoka] mb-3">
        NLP Submission Feed
      </h3>

      {submissions.length === 0 ? (
        <p className="text-xs text-sky-400">No submissions yet</p>
      ) : (
        <>
          {/* Summary stats row */}
          <div className="grid grid-cols-4 gap-2 mb-3">
            <div className="text-center">
              <p className="text-lg font-bold text-sky-900 font-[Fredoka]">
                {totalSubmissions}
              </p>
              <p className="text-[10px] text-sky-500 uppercase tracking-wide">
                Total
              </p>
            </div>
            <div className="text-center">
              <p
                className={`text-lg font-bold font-[Fredoka] ${successRateColor(successRate)}`}
              >
                {successRate}%
              </p>
              <p className="text-[10px] text-sky-500 uppercase tracking-wide">
                Success
              </p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-green-600 font-[Fredoka]">
                {perfectCount}
              </p>
              <p className="text-[10px] text-sky-500 uppercase tracking-wide">
                Perfect
              </p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-sky-900 font-[Fredoka]">
                {avgScore}%
              </p>
              <p className="text-[10px] text-sky-500 uppercase tracking-wide">
                Avg Score
              </p>
            </div>
          </div>

          {/* Daily budget bar (only shown when budget data exists) */}
          {hasBudgetData && (
            <div className="mb-4">
              <div className="flex justify-between text-[10px] text-sky-500 mb-1">
                <span>Daily budget</span>
                <span>
                  {dailyUsed} / {dailyLimit} used
                </span>
              </div>
              <div className="w-full h-2 bg-sky-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(budgetPct, 100)}%`,
                    backgroundColor: budgetBarColor(budgetPct),
                  }}
                />
              </div>
            </div>
          )}

          {/* Submission list */}
          <div className="max-h-[350px] overflow-y-auto space-y-1.5">
            {recentSubs.map((sub, i) => {
              const pct = sub.percentage ?? 0;
              const hasPct = sub.percentage != null;
              const hasChecks =
                sub.checks_passed != null && sub.total_checks != null;

              return (
                <div
                  key={`${sub.timestamp}-${i}`}
                  className="flex items-center gap-2 text-xs py-1.5 border-b border-sky-100/30 last:border-0"
                >
                  {/* Timestamp */}
                  <span className="text-sky-400 font-mono w-12 flex-shrink-0">
                    {utcToCET(sub.timestamp)}
                  </span>

                  {sub.success ? (
                    <>
                      {/* Score bar */}
                      <div className="flex-1 flex items-center gap-2">
                        <div className="flex-1 h-3 bg-sky-50 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-300"
                            style={{
                              width: hasPct ? `${Math.max(pct, 2)}%` : "0%",
                              backgroundColor: hasPct
                                ? scoreBarColor(pct)
                                : "#94a3b8",
                            }}
                          />
                        </div>
                        {/* Score text */}
                        <span className="text-sky-700 font-semibold w-20 text-right flex-shrink-0">
                          {hasChecks
                            ? `${sub.checks_passed}/${sub.total_checks} (${pct}%)`
                            : hasPct
                              ? `${pct}%`
                              : "OK"}
                        </span>
                      </div>
                    </>
                  ) : (
                    /* Failed entry */
                    <div className="flex-1 flex items-center gap-2 min-w-0">
                      <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-bold text-[10px] flex-shrink-0">
                        FAILED
                      </span>
                      <span className="text-red-500 truncate text-[11px]">
                        {sub.error ?? "Unknown error"}
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
