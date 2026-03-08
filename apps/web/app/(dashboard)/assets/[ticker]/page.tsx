'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { use } from 'react';

const FactorRadarScene = dynamic(
  () =>
    import('../../../../src/components/three/scenes/FactorRadarScene').then(
      (m) => m.FactorRadarScene,
    ),
  { ssr: false },
);

export default function AssetDetailPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <Link href="/ranking" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
          ← Ranking
        </Link>
        <h1>{ticker}</h1>
      </header>
      <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
        <Link
          href={`/intelligence/${ticker}`}
          style={{ fontSize: 13, color: 'var(--accent-gold, #fbbf24)', textDecoration: 'none' }}
        >
          Intelligence →
        </Link>
        <Link
          href={`/compare?tickers=${ticker}`}
          style={{ fontSize: 13, color: 'var(--text-secondary)', textDecoration: 'none' }}
        >
          Compare →
        </Link>
      </div>
      <div className="dashboard-scene">
        <FactorRadarScene ticker={ticker} />
      </div>
    </div>
  );
}
