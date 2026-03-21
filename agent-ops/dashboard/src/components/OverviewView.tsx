import { useState, useEffect, useCallback } from "react";
import { useUIStore } from "../stores/uiStore";
import type { RoundData, VizData } from "../types/dashboard";
import { AgentStatusStrip } from "./AgentStatusStrip";
import { NLPSubmissionFeed } from "./NLPSubmissionFeed";
import { LeaderboardView } from "./LeaderboardView";
import { MetricCard } from "./MetricCard";
import { TerrainGrid } from "./TerrainGrid";

// --- Types ---

interface DeadlineInfo {
  label: string;
  time: string;
  passed: boolean;
}

interface MLRound {
  round_number: number;
  status: string;
  our_score: number | null;
  our_rank: number | null;
  queries_used: number;
  queries_total: number;
}

interface MLRoundsData {
  rounds: MLRound[];
  active_round: {
    round_number: number;
    closes_at: string;
    budget_remaining: number;
  } | null;
}

interface NLPSubmission {
  timestamp: string;
  success: boolean;
  daily_used: number | null;
  daily_limit: number | null;
}

interface NLPTaskScores {
  total_score: number;
  tasks_solved: string;
  rank: number;
  rank_of: number;
  submissions_total: number;
  daily_used: number | null;
  daily_limit: number | null;
}

interface LeaderboardSnapshot {
  timestamp: string;
  rows: Record<string, string | number>[];
}

// --- Competition Clock ---

function getDeadlines(): DeadlineInfo[] {
  const now = new Date();
  const deadlines = [
    { label: "CUT-LOSS baseline", time: "2026-03-21T11:00:00Z" },
    { label: "FEATURE FREEZE", time: "2026-03-22T08:00:00Z" },
    { label: "Repo public", time: "2026-03-22T13:45:00Z" },
    { label: "COMPETITION ENDS", time: "2026-03-22T14:00:00Z" },
  ];

  return deadlines.map((d) => {
    const deadline = new Date(d.time);
    return {
      label: d.label,
      time: deadline.toLocaleString("en-GB", {
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }),
      passed: now > deadline,
    };
  });
}

// --- Countdown helpers ---

const COMPETITION_END = new Date("2026-03-22T14:00:00Z"); // 15:00 CET = 14:00 UTC

function formatCountdown(diffMs: number): string {
  if (diffMs <= 0) return "NOW";
  const h = Math.floor(diffMs / 3600000);
  const m = Math.floor((diffMs % 3600000) / 60000);
  const s = Math.floor((diffMs % 60000) / 1000);
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

function timeUntilDeadline(): string {
  const diff = COMPETITION_END.getTime() - Date.now();
  if (diff <= 0) return "ENDED";
  return formatCountdown(diff);
}

function getNextMidnightUTC(): Date {
  const now = new Date();
  const next = new Date(now);
  next.setUTCHours(24, 0, 0, 0);
  return next;
}

// --- Data fetchers ---

async function fetchJSON<T>(url: string): Promise<T | null> {
  try {
    const resp = await fetch(url, { cache: "no-store" });
    if (!resp.ok) return null;
    return (await resp.json()) as T;
  } catch {
    return null;
  }
}

// --- Component ---

export function OverviewView() {
  const setActiveTab = useUIStore((s) => s.setActiveTab);

  // Competition clock
  const [timeLeft, setTimeLeft] = useState(timeUntilDeadline());
  const [deadlines, setDeadlines] = useState(getDeadlines());

  // Per-track countdowns
  const [mlCloses, setMlCloses] = useState<string | null>(null);
  const [rateResets, setRateResets] = useState("");

  // Track data
  const [mlData, setMlData] = useState<MLRoundsData | null>(null);
  const [nlpSubs, setNlpSubs] = useState<NLPSubmission[]>([]);
  const [nlpTaskScores, setNlpTaskScores] = useState<NLPTaskScores | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardSnapshot[]>([]);

  // Mini terrain preview
  const [terrainGrid, setTerrainGrid] = useState<number[][] | null>(null);
  const [terrainLabel, setTerrainLabel] = useState("");

  // --- Fetch all data ---
  const fetchAll = useCallback(async () => {
    const [ml, nlp, nlpScores, lb, viz] = await Promise.all([
      fetchJSON<MLRoundsData>("/data/ml_rounds.json"),
      fetchJSON<NLPSubmission[]>("/data/nlp_submissions.json"),
      fetchJSON<NLPTaskScores>("/data/nlp_task_scores.json"),
      fetchJSON<LeaderboardSnapshot[]>("/data/leaderboard.json"),
      fetchJSON<VizData>("/data/viz_data.json"),
    ]);
    if (ml) setMlData(ml);
    if (nlp) setNlpSubs(nlp);
    if (nlpScores) setNlpTaskScores(nlpScores);
    if (lb) setLeaderboard(lb);

    // Extract the latest round's seed 0 grid for the mini preview
    if (viz) {
      const roundKeys = Object.keys(viz)
        .filter((k) => k.startsWith("round"))
        .sort((a, b) => {
          const numA = parseInt(a.replace("round", ""), 10);
          const numB = parseInt(b.replace("round", ""), 10);
          return numB - numA;
        });
      const latestKey = roundKeys[0];
      if (latestKey) {
        const round = viz[latestKey] as RoundData | undefined;
        if (round?.seeds?.[0]?.grid) {
          setTerrainGrid(round.seeds[0].grid);
          setTerrainLabel(`Round ${round.round_number} - Seed 0`);
        }
      }
    }
  }, []);

  useEffect(() => {
    void fetchAll();
    const interval = setInterval(() => void fetchAll(), 120000); // 2 min
    return () => clearInterval(interval);
  }, [fetchAll]);

  // --- Update countdowns every 30s ---
  useEffect(() => {
    function updateCountdowns() {
      setTimeLeft(timeUntilDeadline());
      setDeadlines(getDeadlines());

      // ML: countdown to active round closes_at
      if (mlData?.active_round?.closes_at) {
        const closesAt = new Date(mlData.active_round.closes_at);
        const diff = closesAt.getTime() - Date.now();
        setMlCloses(formatCountdown(diff));
      } else {
        setMlCloses(null);
      }

      // NLP + CV share the same reset: midnight UTC (01:00 CET)
      const resetDiff = getNextMidnightUTC().getTime() - Date.now();
      setRateResets(formatCountdown(resetDiff));
    }

    updateCountdowns();
    const interval = setInterval(updateCountdowns, 1000);
    return () => clearInterval(interval);
  }, [mlData]);

  // --- Derive track scorecard data ---

  // ML card: latest scored round + weighted total from leaderboard
  const scoredRounds = mlData?.rounds.filter((r) => r.our_score != null) ?? [];
  const latestScoredML = scoredRounds.length > 0 ? scoredRounds[0] : null;
  const mlLatestScore = latestScoredML?.our_score ?? null;
  const mlRank = latestScoredML?.our_rank ?? null;
  const mlRoundsCount = scoredRounds.length;
  const mlBudget = mlData?.active_round?.budget_remaining ?? 0;

  // Leaderboard: find our team
  const latestLB = leaderboard.length > 0 ? leaderboard[leaderboard.length - 1] : null;
  const ourRow = latestLB?.rows.find((r) => {
    const team = String(r["team"] ?? r["lag"] ?? "").toLowerCase();
    return team.includes("kreativ");
  });

  // NLP card: prefer fresh task scores over stale leaderboard
  const nlpScore = nlpTaskScores?.total_score ?? (ourRow ? Number(ourRow["tripletex"] ?? 0) : 0);
  const nlpRank = nlpTaskScores?.rank ?? null;
  const nlpTasksSolved = nlpTaskScores?.tasks_solved ?? null;
  const nlpTotalSubs = nlpTaskScores?.submissions_total ?? nlpSubs.length;

  // ML weighted total from leaderboard (cumulative score across all rounds)
  const mlWeightedTotal = ourRow ? Number(ourRow["astar_island"] ?? 0) : 0;

  // CV card
  const cvScore = ourRow ? Number(ourRow["norgesgruppen"] ?? 0) : 0;

  return (
    <div className="flex-1 flex flex-col overflow-auto p-6 gap-6">

      {/* 1. Competition Clock */}
      <div className="rounded-2xl bg-sky-800/90 backdrop-blur-sm border border-sky-600/50 shadow-xl p-6 text-center">
        <p className="text-sky-300 text-sm font-semibold uppercase tracking-wider">
          Time Remaining
        </p>
        <p className="text-5xl font-bold text-white font-[Fredoka] mt-2">
          {timeLeft}
        </p>
        <p className="text-sky-400 text-xs mt-2">
          Deadline: Sunday 15:00 CET (March 22, 2026)
        </p>

        {/* Key deadlines inline */}
        <div className="flex justify-center gap-6 mt-3 flex-wrap">
          {deadlines.map((d) => (
            <span
              key={d.label}
              className={`text-[11px] ${d.passed ? "text-sky-600 line-through" : "text-sky-300"}`}
            >
              {d.label}: {d.time}
            </span>
          ))}
        </div>
      </div>

      {/* 2. Agent Status Strip */}
      <AgentStatusStrip />

      {/* 3. Per-Track Reset Countdowns */}
      <div className="grid grid-cols-3 gap-4">
        <CountdownPill
          label="ML Round Closes"
          value={mlCloses ?? "No active round"}
          color={mlCloses === "NOW" ? "text-red-500" : "text-sky-800"}
        />
        <CountdownPill
          label="NLP Rate Limit Resets"
          value={rateResets}
          subtitle="01:00 CET"
          color={rateResets === "NOW" ? "text-green-500" : "text-sky-800"}
        />
        <CountdownPill
          label="CV Submissions Reset"
          value={rateResets}
          subtitle="01:00 CET"
          color={rateResets === "NOW" ? "text-green-500" : "text-sky-800"}
        />
      </div>

      {/* 4. Track Scorecards */}
      <div className="grid grid-cols-3 gap-4">
        {/* ML Track */}
        <div className="rounded-2xl bg-white/60 backdrop-blur-sm border border-white/40 shadow-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-3 h-3 rounded-full bg-green-400" />
            <h3 className="text-sm font-bold text-sky-800 font-[Fredoka]">
              Astar Island (ML)
            </h3>
          </div>
          <div className="space-y-1.5">
            <ScoreRow label="Weighted Total" value={mlWeightedTotal > 0 ? mlWeightedTotal.toFixed(1) : "--"} bold />
            <ScoreRow label="Latest Round" value={mlLatestScore != null ? mlLatestScore.toFixed(1) : "--"} />
            <ScoreRow label="Rank (round)" value={mlRank != null ? `#${mlRank}` : "--"} />
            <ScoreRow label="Rounds scored" value={String(mlRoundsCount)} />
            <ScoreRow label="Budget left" value={`${mlBudget} queries`} />
          </div>
        </div>

        {/* NLP Track */}
        <div className="rounded-2xl bg-white/60 backdrop-blur-sm border border-white/40 shadow-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-3 h-3 rounded-full bg-amber-400" />
            <h3 className="text-sm font-bold text-sky-800 font-[Fredoka]">
              Tripletex (NLP)
            </h3>
          </div>
          <div className="space-y-1.5">
            <ScoreRow label="Score" value={nlpScore > 0 ? nlpScore.toFixed(1) : "--"} bold />
            {nlpRank && <ScoreRow label="Rank" value={`#${nlpRank}`} />}
            {nlpTasksSolved && <ScoreRow label="Tasks" value={nlpTasksSolved} />}
            <ScoreRow label="Total subs" value={`${nlpTotalSubs}`} />
            <ScoreRow label="Weight" value="33.33%" />
          </div>
        </div>

        {/* CV Track */}
        <div className="rounded-2xl bg-white/60 backdrop-blur-sm border border-white/40 shadow-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-3 h-3 rounded-full bg-blue-400" />
            <h3 className="text-sm font-bold text-sky-800 font-[Fredoka]">
              NorgesGruppen (CV)
            </h3>
          </div>
          <div className="space-y-1.5">
            <ScoreRow label="Score" value={cvScore > 0 ? cvScore.toFixed(1) : "--"} bold />
            <ScoreRow label="Subs/day" value="10 max" />
            <ScoreRow label="Model" value="YOLO11m" />
            <ScoreRow label="Weight" value="33.33%" />
          </div>
        </div>
      </div>

      {/* Total Score Summary */}
      <div className="flex gap-3">
        <MetricCard
          label="Our Total"
          value={ourRow ? Number(ourRow["total"] ?? 0).toFixed(1) : "--"}
          subtitle={ourRow ? `Rank #${ourRow["rank"] ?? ourRow["#"] ?? "?"}` : "Not on leaderboard"}
          color="text-sky-900"
        />
        {latestLB && ourRow && (() => {
          const top10Last = latestLB.rows[9];
          const top10Score = top10Last ? Number(top10Last["total"] ?? 0) : 0;
          const ourTotal = Number(ourRow["total"] ?? 0);
          const gap = top10Score - ourTotal;
          return (
            <MetricCard
              label="Gap to #10"
              value={gap > 0 ? gap.toFixed(1) : "In top 10!"}
              subtitle={top10Last ? `#10: ${String(top10Last["team"] ?? "?")}` : ""}
              color={gap > 0 ? "text-red-600" : "text-green-600"}
            />
          );
        })()}
        <MetricCard
          label="ML Weighted"
          value={mlWeightedTotal > 0 ? mlWeightedTotal.toFixed(1) : "--"}
          subtitle={mlLatestScore != null ? `Latest: ${mlLatestScore.toFixed(1)}` : "No rounds yet"}
          color="text-green-700"
        />
        <MetricCard
          label="NLP Score"
          value={nlpScore > 0 ? nlpScore.toFixed(1) : "--"}
          subtitle={nlpRank ? `Rank #${nlpRank}` : `${nlpTotalSubs} subs total`}
          color="text-amber-700"
        />
        <MetricCard
          label="CV Score"
          value={cvScore > 0 ? cvScore.toFixed(1) : "--"}
          subtitle="YOLO11m"
          color="text-blue-700"
        />
      </div>

      {/* 5. Mini ML Terrain Preview */}
      {terrainGrid && (
        <div
          className="rounded-2xl bg-white/60 backdrop-blur-sm border border-white/40 shadow-lg p-4 cursor-pointer hover:bg-white/70 transition-colors"
          onClick={() => setActiveTab("ml-explorer")}
        >
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-bold text-sky-800 font-[Fredoka]">
              ML Terrain Preview
            </h3>
            <span className="text-[10px] text-sky-400 uppercase tracking-wide">
              Click to open ML Explorer
            </span>
          </div>
          <div className="w-[200px] h-[200px] mx-auto">
            <TerrainGrid grid={terrainGrid} label={terrainLabel} />
          </div>
        </div>
      )}

      {/* 6. NLP Submission Feed */}
      <NLPSubmissionFeed />

      {/* 7. Leaderboard */}
      <LeaderboardView />
    </div>
  );
}

// --- Sub-components ---

function CountdownPill({
  label,
  value,
  subtitle,
  color,
}: {
  label: string;
  value: string;
  subtitle?: string;
  color: string;
}) {
  return (
    <div className="rounded-xl bg-white/60 backdrop-blur-sm border border-white/40 shadow-md px-4 py-3 text-center">
      <p className="text-[10px] text-sky-500 uppercase tracking-wide font-semibold">
        {label}
      </p>
      <p className={`text-lg font-bold font-[Fredoka] mt-0.5 ${color}`}>
        {value}
      </p>
      {subtitle && (
        <p className="text-[10px] text-sky-400 mt-0.5">{subtitle}</p>
      )}
    </div>
  );
}

function ScoreRow({
  label,
  value,
  bold,
}: {
  label: string;
  value: string;
  bold?: boolean;
}) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-sky-600">{label}</span>
      <span className={`text-sky-800 ${bold ? "font-bold text-sm" : "font-semibold"}`}>
        {value}
      </span>
    </div>
  );
}
