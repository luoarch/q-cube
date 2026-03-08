'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';

const RankingGalaxyScene = dynamic(
  () =>
    import('../../../src/components/three/scenes/RankingGalaxyScene').then(
      (m) => m.RankingGalaxyScene,
    ),
  { ssr: false },
);

export default function RankingPage() {
  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <Link href="/" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
          ← Q³
        </Link>
        <h1>Ranking Galaxy</h1>
      </header>
      <div className="dashboard-scene">
        <RankingGalaxyScene />
      </div>
    </div>
  );
}
