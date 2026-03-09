'use client';

import dynamic from 'next/dynamic';
const UniverseSphereScene = dynamic(
  () =>
    import('../../../src/components/three/scenes/UniverseSphereScene').then(
      (m) => m.UniverseSphereScene,
    ),
  { ssr: false },
);

export default function UniversePage() {
  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <h1>Universe Sphere</h1>
      </header>
      <div className="dashboard-scene">
        <UniverseSphereScene />
      </div>
    </div>
  );
}
