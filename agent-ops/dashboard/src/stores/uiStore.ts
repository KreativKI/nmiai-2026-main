import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { DashboardTab } from "../types/dashboard";

interface UIStore {
  activeTab: DashboardTab;
  setActiveTab: (tab: DashboardTab) => void;
  /** ML tab: which seed is selected (0-4) */
  selectedSeed: number;
  setSelectedSeed: (seed: number) => void;
  /** ML tab: show ground truth overlay */
  showGroundTruth: boolean;
  toggleGroundTruth: () => void;
  /** Canvas fullscreen */
  isCanvasFullscreen: boolean;
  toggleCanvasFullscreen: () => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      activeTab: "overview",
      setActiveTab: (tab) => set({ activeTab: tab }),
      selectedSeed: 0,
      setSelectedSeed: (seed) => set({ selectedSeed: seed }),
      showGroundTruth: false,
      toggleGroundTruth: () => set((s) => ({ showGroundTruth: !s.showGroundTruth })),
      isCanvasFullscreen: false,
      toggleCanvasFullscreen: () => set((s) => ({ isCanvasFullscreen: !s.isCanvasFullscreen })),
    }),
    {
      name: "nmiai-ops-ui",
      partialize: (state) => ({
        activeTab: state.activeTab,
        selectedSeed: state.selectedSeed,
      }),
    },
  ),
);
