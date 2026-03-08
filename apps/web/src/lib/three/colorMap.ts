import { UNKNOWN_SECTOR } from '@q3/shared-contracts';

// Tableau 10 (colorblind-safe)
const PALETTE = [
  '#4e79a7', // blue
  '#f28e2b', // orange
  '#e15759', // red
  '#76b7b2', // teal
  '#59a14f', // green
  '#edc948', // yellow
  '#b07aa1', // purple
  '#ff9da7', // pink
  '#9c755f', // brown
  '#bab0ac', // gray
  '#af7aa1', // mauve
  '#86bcb6', // mint
] as const;

const cache = new Map<string, string>();
let nextIdx = 0;

export function getSectorColor(sector: string): string {
  const key = sector || UNKNOWN_SECTOR;
  const existing = cache.get(key);
  if (existing) return existing;
  const color = PALETTE[nextIdx % PALETTE.length]!;
  nextIdx++;
  cache.set(key, color);
  return color;
}

export function resetSectorColors() {
  cache.clear();
  nextIdx = 0;
}
