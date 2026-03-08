import { create } from 'zustand';

interface ThemeState {
  mode: 'dark' | 'light';
  toggle: () => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  mode: 'dark',
  toggle: () => set((s) => ({ mode: s.mode === 'dark' ? 'light' : 'dark' })),
}));
