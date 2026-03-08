'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';

const QCubeScene = dynamic(
  () => import('../src/components/three/scenes/QCubeScene').then((m) => m.QCubeScene),
  { ssr: false },
);

export default function HomePage() {
  return (
    <div className="hero-page">
      <header className="hero-header">
        <div>
          <h1 className="hero-title">Q³ — Q-Cube</h1>
          <p className="hero-subtitle">Quantity · Quality · Quant Technology</p>
        </div>
        <nav className="hero-nav">
          <Link href="/ranking">Ranking</Link>
          <Link href="/portfolio">Portfolio</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/universe">Universe</Link>
        </nav>
      </header>
      <div className="hero-scene">
        <QCubeScene />
      </div>
    </div>
  );
}
