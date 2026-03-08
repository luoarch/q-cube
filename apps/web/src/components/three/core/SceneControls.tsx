'use client';

import { OrbitControls } from '@react-three/drei';

export function SceneControls({ autoRotate = false }: { autoRotate?: boolean }) {
  return (
    <OrbitControls
      autoRotate={autoRotate}
      autoRotateSpeed={0.5}
      enableDamping
      dampingFactor={0.1}
      minDistance={3}
      maxDistance={25}
      maxPolarAngle={Math.PI * 0.85}
    />
  );
}
