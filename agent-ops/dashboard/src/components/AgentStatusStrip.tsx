import { useState, useEffect, useRef, useCallback } from "react";

// --- Types ---

interface AgentStatus {
  // status.json files use "timestamp", not "last_updated"
  timestamp?: string;
  last_updated?: string;
  score?: number;
  phase?: string;
  state?: string;
  best_submitted_score?: number;
  notes?: string;
}

type AgentState = "active" | "idle" | "unknown";

interface AgentInfo {
  name: string;
  file: string;
  status: AgentStatus | null;
  agentState: AgentState;
  minutesAgo: number | null;
}

// --- Constants ---

const IDLE_THRESHOLD_MS = 30 * 60 * 1000; // 30 minutes
const POLL_INTERVAL_MS = 60 * 1000; // 60 seconds

const AGENTS: { name: string; file: string }[] = [
  { name: "ML", file: "/data/ml_status.json" },
  { name: "NLP", file: "/data/nlp_status.json" },
  { name: "CV", file: "/data/cv_status.json" },
];

const DOT_COLORS: Record<AgentState, string> = {
  active: "#22c55e",
  idle: "#ef4444",
  unknown: "#9ca3af",
};

// --- Audio (shared context to avoid exhausting browser limit of ~6) ---

let sharedAudioCtx: AudioContext | null = null;

function playIdleChime(): void {
  try {
    if (!sharedAudioCtx || sharedAudioCtx.state === "closed") {
      sharedAudioCtx = new AudioContext();
    }
    const ctx = sharedAudioCtx;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    osc.frequency.setValueAtTime(523, ctx.currentTime); // C5
    osc.frequency.exponentialRampToValueAtTime(784, ctx.currentTime + 0.3); // G5
    osc.frequency.exponentialRampToValueAtTime(1047, ctx.currentTime + 0.8); // C6
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 1.5);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 1.5);
  } catch {
    // Audio not available, silently ignore
  }
}

// --- Helpers ---

function parseTimestamp(raw: string): Date | null {
  try {
    const d = new Date(raw);
    if (isNaN(d.getTime())) return null;
    return d;
  } catch {
    return null;
  }
}

function formatCET(date: Date): string {
  // CET = UTC+1
  const utcMs = date.getTime();
  const cetMs = utcMs + 1 * 60 * 60 * 1000;
  const cet = new Date(cetMs);
  const hh = cet.getUTCHours().toString().padStart(2, "0");
  const mm = cet.getUTCMinutes().toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

function determineState(status: AgentStatus | null): {
  agentState: AgentState;
  minutesAgo: number | null;
} {
  // status.json uses "timestamp" field, fall back to "last_updated"
  const rawTs = status?.timestamp ?? status?.last_updated;
  if (!rawTs) {
    return { agentState: "unknown", minutesAgo: null };
  }

  const ts = parseTimestamp(rawTs);
  if (!ts) {
    return { agentState: "unknown", minutesAgo: null };
  }

  const diffMs = Date.now() - ts.getTime();
  const minutesAgo = Math.floor(diffMs / 60000);

  if (diffMs > IDLE_THRESHOLD_MS) {
    return { agentState: "idle", minutesAgo };
  }
  return { agentState: "active", minutesAgo };
}

async function fetchStatus(file: string): Promise<AgentStatus | null> {
  try {
    const resp = await fetch(file, { cache: "no-store" });
    if (!resp.ok) return null;
    const data: unknown = await resp.json();
    if (typeof data === "object" && data !== null) {
      return data as AgentStatus;
    }
    return null;
  } catch {
    return null;
  }
}

// --- Component ---

export function AgentStatusStrip() {
  const [agents, setAgents] = useState<AgentInfo[]>(() =>
    AGENTS.map((a) => ({
      ...a,
      status: null,
      agentState: "unknown" as AgentState,
      minutesAgo: null,
    }))
  );

  // Track previous states to detect transitions
  const prevStatesRef = useRef<Map<string, AgentState>>(new Map());

  const refreshAll = useCallback(async () => {
    const results = await Promise.all(
      AGENTS.map(async (a) => {
        const status = await fetchStatus(a.file);
        const { agentState, minutesAgo } = determineState(status);
        return { ...a, status, agentState, minutesAgo };
      })
    );

    // Check for active -> idle transitions
    for (const agent of results) {
      const prev = prevStatesRef.current.get(agent.name);
      if (prev === "active" && agent.agentState === "idle") {
        // Transition detected: fire notification + sound
        playIdleChime();

        if (Notification.permission === "granted") {
          const mins = agent.minutesAgo ?? 30;
          new Notification(`Agent Idle: ${agent.name}`, {
            body: `${agent.name} agent hasn't updated in ${mins} minutes`,
            icon: undefined,
          });
        }
      }
      prevStatesRef.current.set(agent.name, agent.agentState);
    }

    setAgents(results);
  }, []);

  // Request notification permission, initial fetch, and polling
  useEffect(() => {
    if ("Notification" in window) {
      void Notification.requestPermission();
    }
    void refreshAll();
    const interval = setInterval(() => void refreshAll(), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshAll]);

  return (
    <div className="grid grid-cols-3 gap-3">
      {agents.map((agent) => (
        <AgentCard key={agent.name} agent={agent} />
      ))}
    </div>
  );
}

// --- Card ---

function AgentCard({ agent }: { agent: AgentInfo }) {
  const isIdle = agent.agentState === "idle";

  const borderClass = isIdle
    ? "animate-pulse border-2 border-red-400"
    : "border border-white/40";

  const rawTs = agent.status?.timestamp ?? agent.status?.last_updated;
  const lastActivity = rawTs != null ? parseTimestamp(rawTs) : null;

  const phaseText =
    agent.status?.phase ?? agent.status?.state ?? null;

  return (
    <div
      className={`rounded-xl bg-white/60 backdrop-blur-sm shadow-lg px-4 py-3 ${borderClass}`}
    >
      {/* Header: dot + name */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 ${
            isIdle ? "animate-pulse" : ""
          }`}
          style={{ backgroundColor: DOT_COLORS[agent.agentState] }}
        />
        <span className="text-sm font-bold text-sky-800 font-[Fredoka]">
          {agent.name}
        </span>
        <span className="ml-auto text-[10px] text-sky-500 uppercase tracking-wide">
          {agent.agentState}
        </span>
      </div>

      {/* Last activity */}
      <div className="flex justify-between text-xs mb-1">
        <span className="text-sky-600">Last activity</span>
        <span className="text-sky-800 font-semibold">
          {lastActivity ? formatCET(lastActivity) + " CET" : "--:--"}
        </span>
      </div>

      {/* Minutes ago */}
      {agent.minutesAgo != null && (
        <div className="flex justify-between text-xs mb-1">
          <span className="text-sky-600">Ago</span>
          <span
            className={`font-semibold ${
              isIdle ? "text-red-500" : "text-sky-800"
            }`}
          >
            {agent.minutesAgo}m
          </span>
        </div>
      )}

      {/* Phase/state */}
      {phaseText && (
        <div className="flex justify-between text-xs mb-1">
          <span className="text-sky-600">Phase</span>
          <span className="text-sky-800 font-semibold">{phaseText}</span>
        </div>
      )}

      {/* Score */}
      {agent.status?.score != null && (
        <div className="flex justify-between text-xs">
          <span className="text-sky-600">Score</span>
          <span className="text-sky-800 font-bold">
            {agent.status.score}
          </span>
        </div>
      )}
    </div>
  );
}
