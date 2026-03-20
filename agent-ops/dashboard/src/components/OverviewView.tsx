import { useState, useEffect } from "react";
import { MetricCard } from "./MetricCard";
import { LeaderboardView } from "./LeaderboardView";

interface DeadlineInfo {
  label: string;
  time: string;
  passed: boolean;
}

function getDeadlines(): DeadlineInfo[] {
  const now = new Date();
  const deadlines = [
    { label: "CUT-LOSS baseline", time: "2026-03-21T11:00:00Z" },  // Sat 12:00 CET
    { label: "FEATURE FREEZE", time: "2026-03-22T08:00:00Z" },     // Sun 09:00 CET
    { label: "Repo public", time: "2026-03-22T13:45:00Z" },        // Sun 14:45 CET
    { label: "COMPETITION ENDS", time: "2026-03-22T14:00:00Z" },   // Sun 15:00 CET
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

function timeUntilDeadline(): string {
  const deadline = new Date("2026-03-22T14:00:00Z"); // 15:00 CET = 14:00 UTC
  const now = new Date();
  const diff = deadline.getTime() - now.getTime();
  if (diff <= 0) return "ENDED";
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  return `${hours}h ${minutes}m`;
}

export function OverviewView() {
  const [timeLeft, setTimeLeft] = useState(timeUntilDeadline());
  const [deadlines, setDeadlines] = useState(getDeadlines());

  useEffect(() => {
    const interval = setInterval(() => {
      setTimeLeft(timeUntilDeadline());
      setDeadlines(getDeadlines());
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex-1 flex flex-col overflow-auto p-6 gap-6">
      {/* Competition clock */}
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
      </div>

      {/* Track overview cards */}
      <div className="grid grid-cols-3 gap-4">
        {/* ML Track */}
        <div className="rounded-2xl bg-white/60 backdrop-blur-sm border border-white/40 shadow-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-3 h-3 rounded-full bg-green-400" />
            <h3 className="text-sm font-bold text-sky-800 font-[Fredoka]">
              Astar Island (ML)
            </h3>
          </div>
          <p className="text-xs text-sky-500">
            Terrain prediction, 40x40 grid, 5 seeds
          </p>
          <div className="mt-3 space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-sky-600">Scoring</span>
              <span className="text-sky-800 font-semibold">KL Divergence</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-sky-600">Queries/round</span>
              <span className="text-sky-800 font-semibold">50</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-sky-600">Weight</span>
              <span className="text-sky-800 font-semibold">33.33%</span>
            </div>
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
          <p className="text-xs text-sky-500">
            Object detection, 357 categories, shelf images
          </p>
          <div className="mt-3 space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-sky-600">Scoring</span>
              <span className="text-sky-800 font-semibold">70% det + 30% cls mAP</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-sky-600">Submissions/day</span>
              <span className="text-sky-800 font-semibold">10</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-sky-600">Weight</span>
              <span className="text-sky-800 font-semibold">33.33%</span>
            </div>
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
          <p className="text-xs text-sky-500">
            AI accounting agent, 30 task types, 7 languages
          </p>
          <div className="mt-3 space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-sky-600">Scoring</span>
              <span className="text-sky-800 font-semibold">Field accuracy + tiers</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-sky-600">Rate limit</span>
              <span className="text-sky-800 font-semibold">5/task/day</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-sky-600">Weight</span>
              <span className="text-sky-800 font-semibold">33.33%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Key deadlines */}
      <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4">
        <h3 className="text-sm font-bold text-sky-700 font-[Fredoka] mb-3">
          Key Deadlines
        </h3>
        <div className="space-y-2">
          {deadlines.map((d) => (
            <div
              key={d.label}
              className={`flex items-center justify-between text-xs ${
                d.passed ? "opacity-40 line-through" : ""
              }`}
            >
              <span className="text-sky-700 font-semibold">{d.label}</span>
              <span className="text-sky-500">{d.time}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Leaderboard */}
      <LeaderboardView />

      {/* Metric cards row */}
      <div className="flex gap-3">
        <MetricCard label="Total Tracks" value="3" subtitle="33.33% each" />
        <MetricCard label="Prize Pool" value="1M NOK" subtitle="400K / 300K / 200K + 100K U23" />
        <MetricCard label="Competition" value="NM i AI" subtitle="March 19-22, 2026" />
      </div>
    </div>
  );
}
