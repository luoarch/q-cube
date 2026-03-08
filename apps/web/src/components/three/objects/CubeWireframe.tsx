'use client';

import { useMemo } from 'react';
import { BoxGeometry, EdgesGeometry } from 'three';

import { CUBE_SIZE } from '../../../lib/three/constants';

export function CubeWireframe() {
  const edges = useMemo(() => {
    const box = new BoxGeometry(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE);
    const geo = new EdgesGeometry(box);
    box.dispose();
    return geo;
  }, []);

  return (
    <lineSegments geometry={edges}>
      <lineBasicMaterial color="#94a3b8" opacity={0.15} transparent />
    </lineSegments>
  );
}
