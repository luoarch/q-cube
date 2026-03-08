'use client';

import { useSpring } from '@react-spring/three';
import { useMemo } from 'react';

export function useAnimatedTransition(
  targetPosition: [number, number, number],
  config = { mass: 1, tension: 170, friction: 26 },
) {
  const spring = useSpring({
    position: targetPosition,
    config,
  });

  return spring;
}

export function useAnimatedOpacity(
  visible: boolean,
  config = { mass: 1, tension: 170, friction: 26 },
) {
  const spring = useSpring({
    opacity: visible ? 1 : 0,
    config,
  });

  return spring;
}
