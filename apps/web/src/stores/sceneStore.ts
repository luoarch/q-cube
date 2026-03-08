import { create } from 'zustand';

interface SceneState {
  selectedTicker: string | null;
  hoveredTicker: string | null;
  cameraTarget: [number, number, number] | null;
  filters: {
    sector: string | null;
    quality: string | null;
    liquidity: string | null;
  };
  particleBudget: number;
  select: (ticker: string | null) => void;
  hover: (ticker: string | null) => void;
  setCameraTarget: (target: [number, number, number] | null) => void;
  setFilter: (key: 'sector' | 'quality' | 'liquidity', value: string | null) => void;
  clearFilters: () => void;
}

export const useSceneStore = create<SceneState>((set) => ({
  selectedTicker: null,
  hoveredTicker: null,
  cameraTarget: null,
  filters: { sector: null, quality: null, liquidity: null },
  particleBudget: typeof window !== 'undefined' && window.innerWidth < 768 ? 100 : 500,
  select: (ticker) => set({ selectedTicker: ticker }),
  hover: (ticker) => set({ hoveredTicker: ticker }),
  setCameraTarget: (target) => set({ cameraTarget: target }),
  setFilter: (key, value) => set((s) => ({ filters: { ...s.filters, [key]: value } })),
  clearFilters: () => set({ filters: { sector: null, quality: null, liquidity: null } }),
}));
