import { useState, useEffect, useId } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface LeaderboardEntry {
  [key: string]: string | number;
}

interface LeaderboardSnapshot {
  timestamp: string;
  headers: string[];
  rows: LeaderboardEntry[];
}

const CHART_TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: "rgba(255,255,255,0.95)",
  border: "1px solid rgba(14,165,233,0.2)",
  borderRadius: "12px",
  fontSize: "12px",
  padding: "8px 12px",
};

export function LeaderboardView() {
  const gradientId = useId();
  const [snapshots, setSnapshots] = useState<LeaderboardSnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/leaderboard.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setSnapshots(d as LeaderboardSnapshot[]))
      .catch((e) => setError(String(e)));
  }, []);

  const latest = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;
  const previous = snapshots.length > 1 ? snapshots[snapshots.length - 2] : null;

  // Find our team row
  const ourRow = latest?.rows.find((r) => {
    const team = String(r["team"] ?? r["lag"] ?? "").toLowerCase();
    return team.includes("kreativ");
  });

  // Build score progression data for "our team" across snapshots
  const progressionData = snapshots.map((snap) => {
    const us = snap.rows.find((r) => {
      const team = String(r["team"] ?? r["lag"] ?? "").toLowerCase();
      return team.includes("kreativ");
    });
    const total = us ? Number(us["total"] ?? us["sum"] ?? 0) : 0;
    const time = new Date(snap.timestamp).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
    return { time, score: total };
  });

  // Build delta lookup from previous snapshot
  const prevTotals = new Map<string, number>();
  if (previous) {
    for (const row of previous.rows) {
      const team = String(row["team"] ?? row["lag"] ?? "");
      const total = Number(row["total"] ?? row["sum"] ?? 0);
      prevTotals.set(team, total);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-sky-700 font-[Fredoka]">
          Leaderboard
        </h3>
        {latest && (
          <span className="text-[10px] text-sky-400">
            {new Date(latest.timestamp).toLocaleString("en-GB", {
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
              month: "short",
              day: "numeric",
            })}
            {` | ${snapshots.length} snapshots`}
          </span>
        )}
      </div>

      {error || !latest ? (
        <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4">
          <p className="text-xs text-sky-400">
            {error
              ? "No leaderboard data yet."
              : "Loading..."}
          </p>
          <p className="text-[10px] text-sky-300 mt-1">
            Enter scores: <code className="bg-white/60 px-1 rounded">python3 tools/add_leaderboard_entry.py</code>
          </p>
        </div>
      ) : (
        <>
          {/* Table */}
          <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-sky-400 border-b border-sky-100/50">
                  <th className="text-left py-1 pr-2">#</th>
                  <th className="text-left py-1 pr-4">Team</th>
                  {latest.headers
                    .filter((h) => {
                      const l = h.toLowerCase();
                      return l !== "#" && l !== "rank" && l !== "team" && l !== "lag";
                    })
                    .map((h) => (
                      <th key={h} className="text-right py-1 px-1">{h}</th>
                    ))}
                  {previous && <th className="text-right py-1 pl-2">Delta</th>}
                </tr>
              </thead>
              <tbody>
                {latest.rows.slice(0, 10).map((row, i) => {
                  const rank = row["rank"] ?? row["#"] ?? i + 1;
                  const team = String(row["team"] ?? row["lag"] ?? "?");
                  const total = Number(row["total"] ?? row["sum"] ?? 0);
                  const isUs = team.toLowerCase().includes("kreativ");
                  const prevTotal = prevTotals.get(team);
                  const delta = prevTotal !== undefined ? total - prevTotal : null;

                  const dataCols = latest.headers.filter((h) => {
                    const l = h.toLowerCase();
                    return l !== "#" && l !== "rank" && l !== "team" && l !== "lag";
                  });

                  return (
                    <tr key={i} className={isUs ? "bg-yellow-50/80 font-semibold" : ""}>
                      <td className="py-1 pr-2 text-sky-600">{String(rank)}</td>
                      <td className="py-1 pr-4 text-sky-800 truncate max-w-[200px]">{team}</td>
                      {dataCols.map((h) => (
                        <td key={h} className="py-1 px-1 text-right text-sky-600">
                          {row[h.toLowerCase().replace(" ", "_")] ?? row[h] ?? "-"}
                        </td>
                      ))}
                      {previous && (
                        <td className="py-1 pl-2 text-right">
                          {delta === null ? (
                            <span className="text-sky-300">-</span>
                          ) : delta > 0 ? (
                            <span className="text-green-600 font-semibold">+{delta.toFixed(1)}</span>
                          ) : delta < 0 ? (
                            <span className="text-red-500 font-semibold">{delta.toFixed(1)}</span>
                          ) : (
                            <span className="text-sky-300">-</span>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}

                {/* Our row if not in top 10 */}
                {ourRow && !latest.rows.slice(0, 10).some((r) =>
                  String(r["team"] ?? r["lag"] ?? "").toLowerCase().includes("kreativ")
                ) && (
                  <>
                    <tr>
                      <td colSpan={99} className="py-0.5">
                        <div className="border-t border-dashed border-sky-200" />
                      </td>
                    </tr>
                    <tr className="bg-yellow-50/80 font-semibold">
                      <td className="py-1 pr-2 text-sky-600">
                        {String(ourRow["rank"] ?? ourRow["#"] ?? "?")}
                      </td>
                      <td className="py-1 pr-4 text-sky-800">
                        {String(ourRow["team"] ?? ourRow["lag"] ?? "?")}
                      </td>
                      <td colSpan={99} className="py-1 text-right text-sky-800 font-bold">
                        {String(ourRow["total"] ?? ourRow["sum"] ?? "?")}
                      </td>
                    </tr>
                  </>
                )}
              </tbody>
            </table>
          </div>

          {/* Score progression chart */}
          {progressionData.length > 1 && (
            <div className="rounded-2xl bg-white/50 backdrop-blur-sm border border-white/30 p-4">
              <p className="text-[10px] font-bold text-sky-500 uppercase tracking-wider mb-2">
                Our Score Over Time
              </p>
              <ResponsiveContainer width="100%" height={120}>
                <AreaChart data={progressionData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0284c7" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#0284c7" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 10, fill: "#7dd3fc" }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#7dd3fc" }}
                    tickLine={false}
                    axisLine={false}
                    width={40}
                  />
                  <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                  <Area
                    type="monotone"
                    dataKey="score"
                    stroke="#0284c7"
                    strokeWidth={2}
                    fill={`url(#${gradientId})`}
                    dot={false}
                    animationDuration={300}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}
