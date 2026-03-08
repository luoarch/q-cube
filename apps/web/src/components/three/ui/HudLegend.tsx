'use client';

import { getSectorColor } from '../../../lib/three/colorMap';

import type { RankingItem } from '@q3/shared-contracts';

export function HudLegend({ items }: { items: RankingItem[] }) {
  const sectors = [...new Set(items.map((it) => it.sector))].sort();

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 16,
        left: 16,
        background: 'rgba(10, 14, 26, 0.85)',
        color: '#e2e8f0',
        padding: '12px 16px',
        borderRadius: 10,
        fontSize: 12,
        fontFamily: 'IBM Plex Sans, sans-serif',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        backdropFilter: 'blur(8px)',
        maxHeight: '40vh',
        overflowY: 'auto',
        zIndex: 10,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 8 }}>Setores</div>
      {sectors.map((sector) => (
        <div
          key={sector}
          style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: getSectorColor(sector),
              flexShrink: 0,
            }}
          />
          <span>{sector}</span>
        </div>
      ))}
    </div>
  );
}
