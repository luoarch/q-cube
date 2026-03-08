'use client';

import { useMemo } from 'react';
import { BufferGeometry, Float32BufferAttribute } from 'three';

import type { AssetDetail } from '@q3/shared-contracts';

const FACTOR_COUNT = 5;
const ANGLE_STEP = (Math.PI * 2) / FACTOR_COUNT;
const RADIUS = 2;

export function RadarPolyhedron({
  asset,
  wireframe = false,
  color = '#fbbf24',
}: {
  asset: AssetDetail;
  wireframe?: boolean;
  color?: string;
}) {
  const geo = useMemo(() => {
    const positions: number[] = [];
    const indices: number[] = [];

    // Center point
    positions.push(0, 0, 0);

    // Factor vertices
    for (let i = 0; i < FACTOR_COUNT; i++) {
      const factor = asset.factors[i];
      const r = (factor?.value ?? 0) * RADIUS;
      const angle = i * ANGLE_STEP - Math.PI / 2;
      positions.push(Math.cos(angle) * r, Math.sin(angle) * r, 0);
    }

    // Triangles from center to each edge
    for (let i = 0; i < FACTOR_COUNT; i++) {
      const next = ((i + 1) % FACTOR_COUNT) + 1;
      indices.push(0, i + 1, next);
    }

    const geometry = new BufferGeometry();
    geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    return geometry;
  }, [asset.factors]);

  return (
    <mesh geometry={geo}>
      {wireframe ? (
        <meshBasicMaterial color={color} wireframe transparent opacity={0.6} />
      ) : (
        <meshStandardMaterial color={color} transparent opacity={0.4} side={2} />
      )}
    </mesh>
  );
}
