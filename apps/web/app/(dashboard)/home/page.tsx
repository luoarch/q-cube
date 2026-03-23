'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';

import { useRanking } from '../../../src/hooks/api/useRanking';
import { HomeDisclaimer } from '../../../src/components/MethodologicalDisclaimer';

const QCubeScene = dynamic(
  () => import('../../../src/components/three/scenes/QCubeScene').then((m) => m.QCubeScene),
  { ssr: false },
);

function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        background: 'rgba(17, 24, 39, 0.8)',
        border: '1px solid var(--border-color)',
        borderRadius: 8,
        padding: '0.75rem 1rem',
        backdropFilter: 'blur(8px)',
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'monospace', marginTop: 2, color: 'var(--accent-gold)' }}>
        {value}
      </div>
    </div>
  );
}

export default function HomePage() {
  const { data: rankingResult } = useRanking();
  const items = rankingResult?.data ?? [];

  const topItem = items[0];
  const avgRoic = items.length > 0
    ? items.reduce((sum, it) => sum + (it.returnOnCapital ?? 0), 0) / items.length
    : 0;

  return (
    <div className="dashboard-page" style={{ position: 'relative', overflow: 'hidden' }}>
      {/* 3D cube as background */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
        <QCubeScene />
      </div>

      {/* Overlay content */}
      <div style={{ position: 'relative', zIndex: 1, padding: '2rem', display: 'flex', flexDirection: 'column', height: '100%', pointerEvents: 'none' }}>
        {/* Header */}
        <div style={{ marginBottom: 'auto' }}>
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>
            <span style={{ color: 'var(--accent-gold)' }}>Q³</span>
            <span style={{ fontWeight: 400, color: 'var(--text-secondary)', marginLeft: 8 }}>Q-Cube</span>
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '4px 0 0' }}>
            Quantity · Quality · Quant Technology
          </p>
          <HomeDisclaimer />
        </div>

        {/* Bottom stats + quick actions */}
        <div style={{ pointerEvents: 'auto' }}>
          {/* Stats row */}
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
            <StatChip label="Ativos no Screening" value={String(items.length)} />
            {topItem && (
              <StatChip label="Rank #1 (fórmula)" value={topItem.ticker} />
            )}
            <StatChip label="ROIC Médio" value={avgRoic > 0 ? `${(avgRoic * 100).toFixed(1)}%` : '—'} />
          </div>

          {/* Quick actions */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <Link
              href="/ranking"
              style={{
                padding: '8px 20px',
                background: 'var(--accent-gold)',
                color: '#0a0e1a',
                borderRadius: 6,
                textDecoration: 'none',
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              Ver Ranking
            </Link>
            <Link
              href="/universe"
              style={{
                padding: '8px 20px',
                background: 'rgba(17, 24, 39, 0.8)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                borderRadius: 6,
                textDecoration: 'none',
                fontSize: 13,
                backdropFilter: 'blur(8px)',
              }}
            >
              Universo
            </Link>
            <Link
              href="/chat"
              style={{
                padding: '8px 20px',
                background: 'rgba(17, 24, 39, 0.8)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                borderRadius: 6,
                textDecoration: 'none',
                fontSize: 13,
                backdropFilter: 'blur(8px)',
              }}
            >
              AI Council
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
