'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useState } from 'react';

const BacktestTimelineScene = dynamic(
  () =>
    import('../../../src/components/three/scenes/BacktestTimelineScene').then(
      (m) => m.BacktestTimelineScene,
    ),
  { ssr: false },
);

export default function BacktestPage() {
  const [runId] = useState<string | null>(null);

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <Link href="/" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
          ← Q³
        </Link>
        <h1>Backtest Timeline</h1>
      </header>
      <div className="dashboard-scene">
        <BacktestTimelineScene runId={runId} />
      </div>
    </div>
  );
}
