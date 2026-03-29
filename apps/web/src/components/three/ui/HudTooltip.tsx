'use client';

import { Html } from '@react-three/drei';

import { useSceneStore } from '../../../stores/sceneStore';
import { useAssetPositions } from '../hooks/useAssetPositions';

import type { RankingItem } from '@q3/shared-contracts';

export function HudTooltip({ items }: { items: RankingItem[] }) {
  const hoveredTicker = useSceneStore((s) => s.hoveredTicker);
  const { positions } = useAssetPositions(items);

  if (!hoveredTicker) return null;

  const idx = items.findIndex((it) => it.ticker === hoveredTicker);
  if (idx === -1) return null;

  const item = items[idx]!;
  const x = positions[idx * 3]!;
  const y = positions[idx * 3 + 1]!;
  const z = positions[idx * 3 + 2]!;

  return (
    <Html position={[x, y + 0.3, z]} center style={{ pointerEvents: 'none' }}>
      <div
        style={{
          background: 'rgba(10, 14, 26, 0.92)',
          color: '#e2e8f0',
          padding: '8px 12px',
          borderRadius: 8,
          fontSize: 13,
          fontFamily: 'IBM Plex Sans, sans-serif',
          whiteSpace: 'nowrap',
          border: '1px solid rgba(148, 163, 184, 0.2)',
          backdropFilter: 'blur(8px)',
        }}
      >
        <strong>{item.ticker}</strong>
        <span style={{ opacity: 0.6, marginLeft: 6 }}>{item.name}</span>
        <div style={{ marginTop: 4, display: 'flex', gap: 12, fontSize: 12, opacity: 0.8 }}>
          <span>EY: {(item.earningsYield * 100).toFixed(1)}%</span>
          <span>ROC: {(item.returnOnCapital * 100).toFixed(1)}%</span>
          <span>Rank: #{item.rankWithinModel}</span>
        </div>
      </div>
    </Html>
  );
}
