'use client';

import { useFrame } from '@react-three/fiber';
import { useRef, useMemo } from 'react';
import { type ShaderMaterial, Color } from 'three';

const vertexShader = `
  uniform float uTime;
  varying vec3 vNormal;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    float d = sin(uTime * 2.0 + position.y * 3.0) * 0.02;
    vec3 displaced = position + normal * d;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
  }
`;

const fragmentShader = `
  uniform float uTime;
  uniform vec3 uColor;
  varying vec3 vNormal;
  void main() {
    float intensity = pow(0.7 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.0);
    float pulse = 0.5 + 0.5 * sin(uTime * 3.0);
    float emission = mix(1.0, 2.0, pulse);
    gl_FragColor = vec4(uColor * intensity * emission, intensity * 0.8);
  }
`;

export function ParticleGlow({
  position,
  radius = 0.1,
  color = '#fbbf24',
}: {
  position: [number, number, number];
  radius?: number;
  color?: string;
}) {
  const matRef = useRef<ShaderMaterial>(null);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uColor: { value: new Color(color) },
    }),
    [color],
  );

  useFrame((_, delta) => {
    if (matRef.current) {
      matRef.current.uniforms.uTime!.value += delta;
    }
  });

  return (
    <mesh position={position}>
      <sphereGeometry args={[radius * 1.5, 16, 16]} />
      <shaderMaterial
        ref={matRef}
        uniforms={uniforms}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        transparent
        depthWrite={false}
      />
    </mesh>
  );
}
