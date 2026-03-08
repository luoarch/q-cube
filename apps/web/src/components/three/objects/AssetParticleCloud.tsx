'use client';

import { useFrame } from '@react-three/fiber';
import { useRef, useEffect, useMemo } from 'react';
import {
  Object3D,
  Color,
  type InstancedMesh as InstancedMeshType,
  SphereGeometry,
  MeshStandardMaterial,
  InstancedBufferAttribute,
} from 'three';

import { PARTICLE_SEGMENTS_HI } from '../../../lib/three/constants';
import { useSceneStore } from '../../../stores/sceneStore';
import { useAssetPositions } from '../hooks/useAssetPositions';
import { useRaycastSelection } from '../hooks/useRaycastSelection';

import type { RankingItem } from '@q3/shared-contracts';

const dummy = new Object3D();
const tmpColor = new Color();

export function AssetParticleCloud({ items }: { items: RankingItem[] }) {
  const meshRef = useRef<InstancedMeshType>(null);
  const { positions, colors, sizes } = useAssetPositions(items);
  const { onPointerOver, onPointerOut, onClick, onMiss } = useRaycastSelection(items);
  const hoveredTicker = useSceneStore((s) => s.hoveredTicker);
  const selectedTicker = useSceneStore((s) => s.selectedTicker);

  const count = items.length;

  const geo = useMemo(() => new SphereGeometry(1, PARTICLE_SEGMENTS_HI, PARTICLE_SEGMENTS_HI), []);

  // Set instance matrices from position + size data
  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;

    for (let i = 0; i < count; i++) {
      dummy.position.set(positions[i * 3]!, positions[i * 3 + 1]!, positions[i * 3 + 2]!);
      const s = sizes[i]!;
      dummy.scale.set(s, s, s);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
  }, [positions, sizes, count]);

  // Set instance colors
  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;

    for (let i = 0; i < count; i++) {
      tmpColor.setRGB(colors[i * 3]!, colors[i * 3 + 1]!, colors[i * 3 + 2]!);
      mesh.setColorAt(i, tmpColor);
    }
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [colors, count]);

  // Animate hovered/selected emissive
  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh) return;

    for (let i = 0; i < count; i++) {
      const item = items[i]!;
      const isHovered = item.ticker === hoveredTicker;
      const isSelected = item.ticker === selectedTicker;
      const isTop10 = item.magicFormulaRank <= 10;

      // Modulate scale for hover feedback
      const baseSize = sizes[i]!;
      const scale = isHovered ? baseSize * 1.5 : isSelected ? baseSize * 1.3 : baseSize;

      dummy.position.set(positions[i * 3]!, positions[i * 3 + 1]!, positions[i * 3 + 2]!);
      dummy.scale.set(scale, scale, scale);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);

      // Color: top 10 get gold, hovered gets brighter
      if (isTop10) {
        tmpColor.set('#fbbf24');
      } else {
        tmpColor.setRGB(colors[i * 3]!, colors[i * 3 + 1]!, colors[i * 3 + 2]!);
      }
      if (isHovered) tmpColor.multiplyScalar(1.5);
      mesh.setColorAt(i, tmpColor);
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  });

  if (count === 0) return null;

  return (
    <instancedMesh
      ref={meshRef}
      args={[geo, undefined, count]}
      onPointerOver={onPointerOver}
      onPointerOut={onPointerOut}
      onClick={onClick}
      onPointerMissed={onMiss}
    >
      <meshStandardMaterial vertexColors roughness={0.4} metalness={0.3} toneMapped={false} />
    </instancedMesh>
  );
}
