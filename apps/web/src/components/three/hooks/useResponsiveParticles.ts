'use client';

import { useEffect } from 'react';

import { useSceneStore } from '../../../stores/sceneStore';

export function useResponsiveParticles() {
  const budget = useSceneStore((s) => s.particleBudget);

  useEffect(() => {
    function update() {
      const w = window.innerWidth;
      const newBudget = w < 768 ? 100 : w < 1024 ? 200 : 500;
      if (newBudget !== useSceneStore.getState().particleBudget) {
        useSceneStore.setState({ particleBudget: newBudget });
      }
    }
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  return budget;
}
