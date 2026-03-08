'use client';

import { useRef } from 'react';

import type { ThreeEvent } from '@react-three/fiber';
import type { Mesh } from 'three';

type MeshClickHandler = (e: ThreeEvent<MouseEvent>) => void;
type MeshPointerHandler = (e: ThreeEvent<PointerEvent>) => void;

export function AssetParticle({
  position,
  radius = 0.08,
  color = '#4e79a7',
  emissive = false,
  onClick,
  onPointerOver,
  onPointerOut,
}: {
  position: [number, number, number];
  radius?: number;
  color?: string;
  emissive?: boolean;
  onClick?: MeshClickHandler;
  onPointerOver?: MeshPointerHandler;
  onPointerOut?: MeshPointerHandler;
}) {
  const ref = useRef<Mesh>(null);
  const noop = () => {};

  return (
    <mesh
      ref={ref}
      position={position}
      onClick={onClick ?? noop}
      onPointerOver={onPointerOver ?? noop}
      onPointerOut={onPointerOut ?? noop}
    >
      <sphereGeometry args={[radius, 16, 16]} />
      <meshStandardMaterial
        color={color}
        emissive={emissive ? color : '#000000'}
        emissiveIntensity={emissive ? 2 : 0}
        toneMapped={!emissive}
        roughness={0.4}
        metalness={0.3}
      />
    </mesh>
  );
}
