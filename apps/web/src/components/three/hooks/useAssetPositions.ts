'use client';

import { useMemo } from 'react';
import { Color } from 'three';

import { getSectorColor } from '../../../lib/three/colorMap';
import { createQCubeScales } from '../../../lib/three/scales';

import type { RankingItem } from '@q3/shared-contracts';

interface PositionData {
  positions: Float32Array;
  colors: Float32Array;
  sizes: Float32Array;
}

export function useAssetPositions(items: RankingItem[]): PositionData {
  return useMemo(() => {
    const n = items.length;
    const positions = new Float32Array(n * 3);
    const colors = new Float32Array(n * 3);
    const sizes = new Float32Array(n);

    if (n === 0) return { positions, colors, sizes };

    const scales = createQCubeScales(items);
    const tmpColor = new Color();

    for (let i = 0; i < n; i++) {
      const item = items[i]!;
      positions[i * 3] = scales.x(item.earningsYield);
      positions[i * 3 + 1] = scales.y(item.returnOnCapital);
      positions[i * 3 + 2] = scales.z(item.qualityScore ?? 0.5);

      tmpColor.set(getSectorColor(item.sector));
      colors[i * 3] = tmpColor.r;
      colors[i * 3 + 1] = tmpColor.g;
      colors[i * 3 + 2] = tmpColor.b;

      sizes[i] = scales.radius(item.marketCap);
    }

    return { positions, colors, sizes };
  }, [items]);
}
