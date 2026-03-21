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

/** Recent result from competition page scraper (nlp_task_scores.json) */
interface RecentResult {
  checks_passed: number;
  total_checks: number;
  percentage: number;
  task_header: string;
  time: string;
  duration_s: number;
}

interface NLPTaskScoresData {
  total_score: number;
  tasks_solved: string;
  rank: number;
  submissions_total: number;
  recent_results: RecentResult[];
}

function scoreBarColor(percentage: number): string {
  if (percentage >= 75) return "#22c55e";
  if (percentage >= 25) return "#f59e0b";
  return "#ef4444";
}

function successRateColor(rate: number): string {
  if (rate >= 75) return "text-green-600";
  if (rate >= 50) return "text-amber-600";
  return "text-red-600";
}

export function NLPSubmissionFeed() {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [competitionResults, setCompetitionResults] = useState<RecentResult[]>([]);
  const [competitionMeta, setCompetitionMeta] = useState<{
    total: number;
    solved: string;
    rank: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [subsResp, scoresResp] = await Promise.all([
        fetch("/data/nlp_submissions.json").catch(() => null),
        fetch("/data/nlp_task_scores.json", { cache: "no-store" }).catch(() => null),
      ]);

      if (subsResp?.ok) {
        const data: Submission[] = await subsResp.json();
        setSubmissions(data);
      }

      if (scoresResp?.ok) {
        const data = (await scoresResp.json()) as NLPTaskScoresData;
        if (data.recent_results) setCompetitionResults(data.recent_results);
        setCompetitionMeta({
          total: data.submissions_total,
          solved: data.tasks_solved,
          rank: data.rank,
        });
      }
    } catch {
      setSubmissions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Use competition results if available (they have actual check counts),
  // fall back to local submission log
  const hasCompetitionData = competitionResults.length > 0;
  const displayResults = hasCompetitionData ? competitionResults : [];

  // Stats from competition data or local submissions
  const totalSubmissions = competitionMeta?.total ?? submissions.length;
  const scored = hasCompetitionData
    ? competitionResults
    : submissions.filter((s) => s.percentage != null);
  const perfectCount = scored.filter((s) => s.percentage === 100).length;
  const avgScore = scored.length > 0
    ? Math.round(scored.reduce((sum, s) => sum + (s.percentage ?? 0), 0) / scored.length)
    : 0;
  const successRate = scored.length > 0
    ? Math.round((scored.filter((s) => s.percentage != null && s.percentage > 0).length / scored.length) * 100)
    : 0;

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

      {totalSubmissions === 0 ? (
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

          {/* Competition results (scraped from competition page, have check counts) */}
          {hasCompetitionData && (
            <div className="max-h-[350px] overflow-y-auto space-y-1.5">
              {displayResults.map((result, i) => {
                const pct = result.percentage;
                return (
                  <div
                    key={`comp-${i}`}
                    className="flex items-center gap-2 text-xs py-1.5 border-b border-sky-100/30 last:border-0"
                  >
                    {/* Time */}
                    <span className="text-sky-400 font-mono w-16 flex-shrink-0">
                      {result.time}
                    </span>
                    {/* Score bar */}
                    <div className="flex-1 flex items-center gap-2">
                      <div className="flex-1 h-3 bg-sky-50 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-300"
                          style={{
                            width: `${Math.max(pct, 2)}%`,
                            backgroundColor: scoreBarColor(pct),
                          }}
                        />
                      </div>
                      {/* Score text */}
                      <span className="text-sky-700 font-semibold w-24 text-right flex-shrink-0">
                        {result.checks_passed}/{result.total_checks} ({pct}%)
                      </span>
                    </div>
                    {/* Duration */}
                    <span className="text-sky-400 text-[10px] w-10 text-right flex-shrink-0">
                      {result.duration_s.toFixed(0)}s
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Local submission log fallback (when no competition data) */}
          {!hasCompetitionData && submissions.length > 0 && (
            <div className="max-h-[350px] overflow-y-auto space-y-1.5">
              {[...submissions].reverse().slice(0, 20).map((sub, i) => {
                const pct = sub.percentage ?? 0;
                const hasPct = sub.percentage != null;
                const hasChecks =
                  sub.checks_passed != null && sub.total_checks != null;

                return (
                  <div
                    key={`${sub.timestamp}-${i}`}
                    className="flex items-center gap-2 text-xs py-1.5 border-b border-sky-100/30 last:border-0"
                  >
                    <span className="text-sky-400 font-mono w-12 flex-shrink-0">
                      {utcToCET(sub.timestamp)}
                    </span>

                    {sub.success ? (
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
                        <span className="text-sky-700 font-semibold w-20 text-right flex-shrink-0">
                          {hasChecks
                            ? `${sub.checks_passed}/${sub.total_checks} (${pct}%)`
                            : hasPct
                              ? `${pct}%`
                              : "OK"}
                        </span>
                      </div>
                    ) : (
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
          )}
        </>
      )}
    </div>
  );
}

function utcToCET(isoString: string): string {
  const d = new Date(isoString);
  const cetMs = d.getTime() + 1 * 60 * 60 * 1000;
  const cet = new Date(cetMs);
  const hh = String(cet.getUTCHours()).padStart(2, "0");
  const mm = String(cet.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}
