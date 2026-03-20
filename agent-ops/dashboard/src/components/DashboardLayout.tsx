import { useState, useEffect, useCallback } from "react";
import type { DashboardTab } from "../types/dashboard";
import { useUIStore } from "../stores/uiStore";
import { OverviewView } from "./OverviewView";
import { MLView } from "./MLView";
import { CVView } from "./CVView";
import { NLPView } from "./NLPView";

const TABS: { id: DashboardTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "ml", label: "Astar Island" },
  { id: "cv", label: "NorgesGruppen" },
  { id: "nlp", label: "Tripletex" },
];

const REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes

export function DashboardLayout() {
  const activeTab = useUIStore((s) => s.activeTab);
  const setActiveTab = useUIStore((s) => s.setActiveTab);
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastRefresh, setLastRefresh] = useState<string>(
    new Date().toLocaleTimeString("en-GB", { hour12: false }),
  );

  const triggerRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setLastRefresh(new Date().toLocaleTimeString("en-GB", { hour12: false }));
  }, []);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(triggerRefresh, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [triggerRefresh]);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Top nav bar */}
      <header className="flex items-center justify-between px-6 py-3 bg-white/50 backdrop-blur-md border-b border-white/30">
        <button
          onClick={() => setActiveTab("overview")}
          className="flex items-center gap-3 hover:opacity-80 transition-opacity"
        >
          <img
            src="/logos/KREATIV-KI-3.svg"
            alt="Kreativ KI"
            className="h-7"
          />
          <span className="text-sky-300">|</span>
          <h1 className="text-xl font-bold text-sky-800 font-[Fredoka] tracking-tight">
            NM i AI 2026
          </h1>
        </button>

        {/* Tab pills */}
        <nav className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-all ${
                activeTab === tab.id
                  ? "bg-sky-800 text-white shadow-md"
                  : "text-sky-600 hover:bg-white/60"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <button
            onClick={triggerRefresh}
            className="px-3 py-1.5 rounded-full bg-white/60 text-xs font-semibold text-sky-600 hover:bg-white/80 transition-colors"
          >
            Refresh
          </button>
          <span className="text-[10px] text-sky-400">{lastRefresh}</span>
        </div>
      </header>

      {/* Tab content — refreshKey forces re-mount to reload data */}
      <div key={refreshKey} className="flex-1 flex flex-col overflow-hidden">
        {activeTab === "overview" && <OverviewView />}
        {activeTab === "ml" && <MLView />}
        {activeTab === "cv" && <CVView />}
        {activeTab === "nlp" && <NLPView />}
      </div>
    </div>
  );
}
