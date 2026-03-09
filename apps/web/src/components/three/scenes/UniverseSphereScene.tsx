'use client';

import { useMemo } from 'react';

import { useUniverse } from '../../../hooks/api/useUniverse';
import { getSectorColor } from '../../../lib/three/colorMap';
import { SceneCamera } from '../core/SceneCamera';
import { SceneCanvas } from '../core/SceneCanvas';
import { SceneControls } from '../core/SceneControls';
import { SceneLights } from '../core/SceneLights';
import { NestedSphere } from '../objects/NestedSphere';
import { ScreenReaderDescription } from '../ui/ScreenReaderDescription';

// Golden ratio spiral for distributing sectors in 3D
const PHI = (1 + Math.sqrt(5)) / 2;

function spiralPosition(index: number, count: number, outerR: number): [number, number, number] {
  const y = 1 - (index / (count - 1 || 1)) * 2;
  const rSlice = Math.sqrt(1 - y * y);
  const theta = (2 * Math.PI * index) / PHI;
  return [
    Math.cos(theta) * rSlice * outerR * 0.7,
    y * outerR * 0.7,
    Math.sin(theta) * rSlice * outerR * 0.7,
  ];
}

function SphereInner() {
  const { data: universe } = useUniverse();

  const sectors = useMemo(() => {
    if (!universe?.sectors.length) return [];
    const maxMc = Math.max(...universe.sectors.map((s) => s.marketCap), 1);
    return universe.sectors.map((s, i) => ({
      ...s,
      position: spiralPosition(i, universe.sectors.length, 3),
      radius: 0.3 + (s.marketCap / maxMc) * 1.2,
      color: getSectorColor(s.name),
    }));
  }, [universe]);

  if (!universe) return null;

  return (
    <>
      <SceneCamera />
      <SceneLights />
      <SceneControls autoRotate />

      {/* Outer universe wireframe */}
      <NestedSphere position={[0, 0, 0]} radius={3.5} color="#94a3b8" opacity={0.05} />

      {/* Sector spheres */}
      {sectors.map((s) => (
        <NestedSphere
          key={s.name}
          position={s.position}
          radius={s.radius}
          color={s.color}
          label={s.name}
          opacity={0.12}
        />
      ))}
    </>
  );
}

export function UniverseSphereScene() {
  const { isLoading, error } = useUniverse();

  if (error) {
    return (
      <div className="scene-container">
        <div className="scene-error">
          <p>Erro ao carregar universo.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="scene-container">
      <ScreenReaderDescription description="Universe Sphere: setores como esferas aninhadas" />
      <SceneCanvas className="scene-canvas" frameloop="demand">
        <SphereInner />
      </SceneCanvas>
      {isLoading && <div className="scene-loading-overlay">Carregando...</div>}
    </div>
  );
}
