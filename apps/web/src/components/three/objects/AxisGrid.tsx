'use client';

import { Text } from '@react-three/drei';
import { useMemo } from 'react';
import { BufferGeometry, Float32BufferAttribute, LineBasicMaterial, Line } from 'three';

import { HALF_CUBE, AXIS_LABELS } from '../../../lib/three/constants';

const LABEL_OFFSET = 0.4;

function AxisLine({ points }: { points: Float32Array }) {
  const line = useMemo(() => {
    const g = new BufferGeometry();
    g.setAttribute('position', new Float32BufferAttribute(points, 3));
    const m = new LineBasicMaterial({ color: '#94a3b8', opacity: 0.3, transparent: true });
    return new Line(g, m);
  }, [points]);

  return <primitive object={line} />;
}

export function AxisGrid() {
  const labelColor = '#e2e8f0';

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

      {/* X label */}
      <Text
        position={[HALF_CUBE + LABEL_OFFSET, -HALF_CUBE, -HALF_CUBE]}
        fontSize={0.18}
        color={labelColor}
        anchorX="left"
      >
        {AXIS_LABELS.x}
      </Text>

      {/* Y label */}
      <Text
        position={[-HALF_CUBE, HALF_CUBE + LABEL_OFFSET, -HALF_CUBE]}
        fontSize={0.18}
        color={labelColor}
        anchorX="center"
      >
        {AXIS_LABELS.y}
      </Text>

      {/* Z label */}
      <Text
        position={[-HALF_CUBE, -HALF_CUBE, HALF_CUBE + LABEL_OFFSET]}
        fontSize={0.18}
        color={labelColor}
        anchorX="left"
      >
        {AXIS_LABELS.z}
      </Text>
    </group>
  );
}
