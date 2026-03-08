'use client';

import { useThree } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import { Vector3 } from 'three';

import { useSceneStore } from '../../../stores/sceneStore';

export function useCameraTransition() {
  const camera = useThree((s) => s.camera);
  const cameraTarget = useSceneStore((s) => s.cameraTarget);
  const targetRef = useRef(new Vector3());

  useEffect(() => {
    if (!cameraTarget) return;
    targetRef.current.set(...cameraTarget);

    // Simple lerp towards target (spring animation is handled by OrbitControls damping)
    const targetPos = targetRef.current.clone().add(new Vector3(3, 2, 3));
    camera.position.lerp(targetPos, 0.1);
    camera.lookAt(targetRef.current);
  }, [cameraTarget, camera]);
}
