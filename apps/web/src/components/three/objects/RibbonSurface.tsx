'use client';

import { useMemo } from 'react';
import { BufferGeometry, Float32BufferAttribute, Color } from 'three';

interface CurvePoint {
  date: string;
  value: number;
}

export function RibbonSurface({
  curve,
  zOffset = 0,
  width = 0.3,
  color = '#4e79a7',
}: {
  curve: CurvePoint[];
  zOffset?: number;
  width?: number;
  color?: string;
}) {
  const geo = useMemo(() => {
    if (curve.length < 2) return null;

    const n = curve.length;
    const positions: number[] = [];
    const colors: number[] = [];
    const indices: number[] = [];

    const maxVal = Math.max(...curve.map((p) => p.value));
    const minVal = Math.min(...curve.map((p) => p.value));
    const range = maxVal - minVal || 1;

    const baseColor = new Color(color);
    const lowColor = new Color('#ef4444');
    const highColor = new Color('#22c55e');

    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * 5 - 2.5;
      const y = ((curve[i]!.value - minVal) / range) * 5 - 2.5;
      const t = (curve[i]!.value - minVal) / range;

      const c = lowColor.clone().lerp(highColor, t);

      // Top vertex
      positions.push(x, y, zOffset - width / 2);
      colors.push(c.r, c.g, c.b);

      // Bottom vertex
      positions.push(x, y, zOffset + width / 2);
      colors.push(c.r, c.g, c.b);

      if (i < n - 1) {
        const base = i * 2;
        indices.push(base, base + 1, base + 2);
        indices.push(base + 1, base + 3, base + 2);
      }
    }

    const geometry = new BufferGeometry();
    geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));
    geometry.setAttribute('color', new Float32BufferAttribute(colors, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    return geometry;
  }, [curve, zOffset, width, color]);

  if (!geo) return null;

  return (
    <mesh geometry={geo}>
      <meshStandardMaterial vertexColors side={2} transparent opacity={0.8} />
    </mesh>
  );
}
