'use client';

import { useMemo } from 'react';
import { BufferGeometry, Float32BufferAttribute, LineBasicMaterial, Line } from 'three';

import { HALF_CUBE } from '../../../lib/three/constants';

function AxisLine({ points }: { points: Float32Array }) {
  const line = useMemo(() => {
    const g = new BufferGeometry();
    g.setAttribute('position', new Float32BufferAttribute(points, 3));
    const m = new LineBasicMaterial({ color: '#94a3b8', opacity: 0.2, transparent: true });
    return new Line(g, m);
  }, [points]);

  return <primitive object={line} />;
}

export function AxisGrid() {
  return (
    <group>
      {/* X axis */}
      <AxisLine
        points={
          new Float32Array([-HALF_CUBE, -HALF_CUBE, -HALF_CUBE, HALF_CUBE, -HALF_CUBE, -HALF_CUBE])
        }
      />
      {/* Y axis */}
      <AxisLine
        points={
          new Float32Array([-HALF_CUBE, -HALF_CUBE, -HALF_CUBE, -HALF_CUBE, HALF_CUBE, -HALF_CUBE])
        }
      />
      {/* Z axis */}
      <AxisLine
        points={
          new Float32Array([-HALF_CUBE, -HALF_CUBE, -HALF_CUBE, -HALF_CUBE, -HALF_CUBE, HALF_CUBE])
        }
      />
    </group>
  );
}
