'use client';

import { useCallback } from 'react';

import { announceSelection } from '../../../lib/three/accessibility';
import { useSceneStore } from '../../../stores/sceneStore';

import type { ThreeEvent } from '@react-three/fiber';

export function useRaycastSelection(items: { ticker: string }[]) {
  const select = useSceneStore((s) => s.select);
  const hover = useSceneStore((s) => s.hover);

  const onPointerOver = useCallback(
    (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      const idx = e.instanceId;
      if (idx !== undefined && items[idx]) {
        hover(items[idx].ticker);
        document.body.style.cursor = 'pointer';
      }
    },
    [items, hover],
  );

  const onPointerOut = useCallback(() => {
    hover(null);
    document.body.style.cursor = 'auto';
  }, [hover]);

  const onClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      const idx = e.instanceId;
      if (idx !== undefined && items[idx]) {
        const ticker = items[idx].ticker;
        select(ticker);
        announceSelection(ticker);
      }
    },
    [items, select],
  );

  const onMiss = useCallback(() => {
    select(null);
    announceSelection(null);
  }, [select]);

  return { onPointerOver, onPointerOut, onClick, onMiss };
}
