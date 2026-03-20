import type { DashboardTab } from "../types/dashboard";
import { useUIStore } from "../stores/uiStore";
import { OverviewView } from "./OverviewView";
import { MLView } from "./MLView";
import { CVView } from "./CVView";
import { NLPView } from "./NLPView";

const TABS: { id: DashboardTab; label: string; emoji: string }[] = [
  { id: "overview", label: "Overview", emoji: "" },
  { id: "ml", label: "Astar Island", emoji: "" },
  { id: "cv", label: "NorgesGruppen", emoji: "" },
  { id: "nlp", label: "Tripletex", emoji: "" },
];

export function DashboardLayout() {
  const activeTab = useUIStore((s) => s.activeTab);
  const setActiveTab = useUIStore((s) => s.setActiveTab);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Top nav bar */}
      <header className="flex items-center justify-between px-6 py-3 bg-white/50 backdrop-blur-md border-b border-white/30">
        <button
          onClick={() => setActiveTab("overview")}
          className="flex items-center gap-3 hover:opacity-80 transition-opacity"
        >
          <h1 className="text-xl font-bold text-sky-800 font-[Fredoka] tracking-tight">
            NM i AI 2026 - Ops
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

        <div className="text-xs text-sky-500 font-medium">
          Butler Agent
        </div>
      </header>

      {/* Tab content */}
      {activeTab === "overview" && <OverviewView />}
      {activeTab === "ml" && <MLView />}
      {activeTab === "cv" && <CVView />}
      {activeTab === "nlp" && <NLPView />}
    </div>
  );
}
