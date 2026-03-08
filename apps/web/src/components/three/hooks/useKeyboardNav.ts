'use client';

import { useEffect } from 'react';

import { announceSelection } from '../../../lib/three/accessibility';
import { useSceneStore } from '../../../stores/sceneStore';

import type { RankingItem } from '@q3/shared-contracts';

export function useKeyboardNav(items: RankingItem[]) {
  const selectedTicker = useSceneStore((s) => s.selectedTicker);
  const select = useSceneStore((s) => s.select);

  useEffect(() => {
    if (items.length === 0) return;

    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        select(null);
        announceSelection(null);
        return;
      }
      if (e.key === 'Tab' && !e.shiftKey) {
        e.preventDefault();
        const currentIdx = selectedTicker
          ? items.findIndex((it) => it.ticker === selectedTicker)
          : -1;
        const nextIdx = (currentIdx + 1) % items.length;
        const next = items[nextIdx]!.ticker;
        select(next);
        announceSelection(next);
        return;
      }
      if (e.key === 'r' || e.key === 'R') {
        select(null);
        announceSelection(null);
      }
    }

    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [items, selectedTicker, select]);
}
