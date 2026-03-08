'use client';

import { Line } from '@react-three/drei';
import { useMemo } from 'react';
import { QuadraticBezierCurve3, Vector3 } from 'three';

export function ConnectionLine({
  start,
  end,
  color = '#4e79a7',
  opacity = 0.3,
}: {
  start: [number, number, number];
  end: [number, number, number];
  color?: string;
  opacity?: number;
}) {
  const points = useMemo(() => {
    const mid = new Vector3(
      (start[0] + end[0]) / 2,
      Math.max(start[1], end[1]) + 0.5,
      (start[2] + end[2]) / 2,
    );
    const curve = new QuadraticBezierCurve3(new Vector3(...start), mid, new Vector3(...end));
    return curve.getPoints(20);
  }, [start, end]);

  return <Line points={points} color={color} lineWidth={1} transparent opacity={opacity} />;
}
