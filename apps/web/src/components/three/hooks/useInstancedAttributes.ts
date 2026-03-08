'use client';

import { useEffect, useRef } from 'react';
import { InstancedBufferAttribute, type InstancedMesh } from 'three';

export function useInstancedAttributes(
  meshRef: React.RefObject<InstancedMesh | null>,
  attributeName: string,
  data: Float32Array,
  itemSize: number,
) {
  const attrRef = useRef<InstancedBufferAttribute | null>(null);

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh || data.length === 0) return;

    if (!attrRef.current) {
      attrRef.current = new InstancedBufferAttribute(data, itemSize);
      mesh.geometry.setAttribute(attributeName, attrRef.current);
    } else {
      attrRef.current.set(data);
      attrRef.current.needsUpdate = true;
    }
  }, [meshRef, attributeName, data, itemSize]);
}
