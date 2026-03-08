import { scaleSqrt } from 'd3-scale';

export function marketCapToRadius(marketCap: number, domain: [number, number]): number {
  return scaleSqrt().domain(domain).range([0.02, 0.12]).clamp(true)(Math.max(marketCap, 1));
}
