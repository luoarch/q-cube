'use client';

import dynamic from 'next/dynamic';
const PortfolioConstellationScene = dynamic(
  () =>
    import('../../../src/components/three/scenes/PortfolioConstellationScene').then(
      (m) => m.PortfolioConstellationScene,
    ),
  { ssr: false },
);

export default function PortfolioPage() {
  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <h1>Portfolio Constellation</h1>
      </header>
      <div className="dashboard-scene">
        <PortfolioConstellationScene />
      </div>
    </div>
  );
}
