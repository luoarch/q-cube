'use client';

import { Text } from '@react-three/drei';

import type { ReactNode } from 'react';

export function NestedSphere({
  position,
  radius,
  color,
  label,
  opacity = 0.15,
  children,
}: {
  position: [number, number, number];
  radius: number;
  color: string;
  label?: string;
  opacity?: number;
  children?: ReactNode;
}) {
  return (
    <group position={position}>
      <mesh>
        <sphereGeometry args={[radius, 32, 32]} />
        <meshStandardMaterial color={color} transparent opacity={opacity} wireframe />
      </mesh>
      {label && (
        <Text
          position={[0, radius + 0.2, 0]}
          fontSize={Math.max(0.12, radius * 0.15)}
          color="#e2e8f0"
          anchorX="center"
        >
          {label}
        </Text>
      )}
      {children}
    </group>
  );
}
