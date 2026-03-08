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
      <div className="dashboard-scene">
        <FactorRadarScene ticker={ticker} />
      </div>
    </div>
  );
}
