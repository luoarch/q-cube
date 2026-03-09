import { scaleLinear, scaleSqrt, scaleLog } from 'd3-scale';

import { HALF_CUBE } from './constants';

import type { RankingItem } from '@q3/shared-contracts';

function extent(items: RankingItem[], fn: (d: RankingItem) => number): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const item of items) {
    const v = fn(item);
    if (v < min) min = v;
    if (v > max) max = v;
  }
  if (min === Infinity) return [0, 1];
  if (min === max) return [min - 1, max + 1];
  return [min, max];
}

/**
 * Clamp extent at p5/p95 percentiles to prevent extreme outliers
 * from compressing all points into a tiny cluster.
 */
function robustExtent(
  items: RankingItem[],
  fn: (d: RankingItem) => number,
  pLow = 0.02,
  pHigh = 0.98,
): [number, number] {
  const sorted = items.map(fn).sort((a, b) => a - b);
  const lo = sorted[Math.floor(sorted.length * pLow)] ?? sorted[0]!;
  const hi = sorted[Math.floor(sorted.length * pHigh)] ?? sorted[sorted.length - 1]!;
  if (lo === hi) return [lo - 1, hi + 1];
  return [lo, hi];
}

export function createQCubeScales(items: RankingItem[]) {
  const eyExtent = robustExtent(items, (d) => d.earningsYield);
  const rocExtent = robustExtent(items, (d) => d.returnOnCapital);
  const mcExtent = extent(items, (d) => Math.max(d.marketCap, 1));

  const x = scaleLinear().domain(eyExtent).range([-HALF_CUBE, HALF_CUBE]).clamp(true);
  const y = scaleLinear().domain(rocExtent).range([-HALF_CUBE, HALF_CUBE]).clamp(true);
  const z = scaleLinear().domain([0, 1]).range([-HALF_CUBE, HALF_CUBE]).clamp(true);
  const radius = scaleSqrt().domain(mcExtent).range([0.02, 0.12]).clamp(true);

  return { x, y, z, radius };
}

export function createGalaxyScales(items: RankingItem[]) {
  const eyExtent = extent(items, (d) => d.earningsYield);
  const rocExtent = extent(items, (d) => d.returnOnCapital);
  const mcValues = items.map((d) => Math.max(d.marketCap, 1));
  const mcMin = Math.min(...mcValues);
  const mcMax = Math.max(...mcValues);

  const x = scaleLinear().domain(eyExtent).range([-HALF_CUBE, HALF_CUBE]).clamp(true);
  const y = scaleLinear().domain(rocExtent).range([-HALF_CUBE, HALF_CUBE]).clamp(true);
  const z = scaleLog()
    .domain([Math.max(mcMin, 1), Math.max(mcMax, 2)])
    .range([-HALF_CUBE, HALF_CUBE])
    .clamp(true);

  return { x, y, z };
}
