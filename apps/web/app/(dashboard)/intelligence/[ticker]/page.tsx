'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { use } from 'react';

const CompanyIntelligenceScene = dynamic(
  () =>
    import('../../../../src/components/three/scenes/CompanyIntelligenceScene').then(
      (m) => m.CompanyIntelligenceScene,
    ),
  { ssr: false },
);

const IntelligencePanel = dynamic(
  () =>
    import('../../../../src/components/three/ui/IntelligencePanel').then(
      (m) => m.IntelligencePanel,
    ),
  { ssr: false },
);

export default function IntelligencePage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <Link href={`/assets/${ticker}`} style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
          ← {ticker}
        </Link>
        <h1>Intelligence — {ticker}</h1>
      </header>
      <div className="dashboard-scene" style={{ position: 'relative' }}>
        <CompanyIntelligenceScene ticker={ticker} />
        <IntelligencePanel ticker={ticker} />
      </div>
    </div>
  );
}
