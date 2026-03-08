'use client';

import { PerspectiveCamera } from '@react-three/drei';

import { DEFAULT_CAMERA_POSITION } from '../../../lib/three/constants';

export function SceneCamera() {
  return (
    <PerspectiveCamera
      makeDefault
      position={DEFAULT_CAMERA_POSITION}
      fov={50}
      near={0.1}
      far={100}
    />
  );
}
