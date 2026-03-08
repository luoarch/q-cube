'use client';

import type { BacktestMetrics } from '@q3/shared-contracts';

export function HudMetricsCard({ metrics }: { metrics: BacktestMetrics }) {
  return (
    <div
      style={{
        position: 'absolute',
        top: 16,
        right: 16,
        display: 'flex',
        gap: 8,
        zIndex: 10,
      }}
    >
      <KpiCard
        label="CAGR"
        value={`${(metrics.cagr * 100).toFixed(1)}%`}
        positive={metrics.cagr > 0}
      />
      <KpiCard label="Sharpe" value={metrics.sharpe.toFixed(2)} positive={metrics.sharpe > 1} />
      <KpiCard
        label="Max DD"
        value={`${(metrics.maxDrawdown * 100).toFixed(1)}%`}
        positive={false}
      />
      <KpiCard
        label="Hit Rate"
        value={`${(metrics.hitRate * 100).toFixed(0)}%`}
        positive={metrics.hitRate > 0.5}
      />
    </div>
  );
}

function KpiCard({ label, value, positive }: { label: string; value: string; positive: boolean }) {
  return (
    <div
      style={{
        background: 'rgba(10, 14, 26, 0.85)',
        border: '1px solid var(--border-color, rgba(148,163,184,0.15))',
        borderRadius: 8,
        padding: '8px 14px',
        fontFamily: 'IBM Plex Sans, sans-serif',
        backdropFilter: 'blur(8px)',
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--text-secondary, #94a3b8)', marginBottom: 2 }}>
        {label}
      </div>
      <div
        style={{
          fontSize: 16,
          fontWeight: 600,
          color: positive ? '#4ade80' : '#f87171',
        }}
      >
        {value}
      </div>
    </div>
  );
}
