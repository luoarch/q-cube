'use client';

import { useRanking } from '../../../hooks/api/useRanking';
import { PostProcessing } from '../core/PostProcessing';
import { SceneCamera } from '../core/SceneCamera';
import { SceneCanvas } from '../core/SceneCanvas';
import { SceneControls } from '../core/SceneControls';
import { SceneLights } from '../core/SceneLights';
import { useKeyboardNav } from '../hooks/useKeyboardNav';
import { useResponsiveParticles } from '../hooks/useResponsiveParticles';
import { AssetParticleCloud } from '../objects/AssetParticleCloud';
import { AxisGrid } from '../objects/AxisGrid';
import { CubeWireframe } from '../objects/CubeWireframe';
import { HudLegend } from '../ui/HudLegend';
import { HudTooltip } from '../ui/HudTooltip';
import { ScreenReaderDescription } from '../ui/ScreenReaderDescription';

function QCubeInner() {
  const { data: items = [] } = useRanking();
  const budget = useResponsiveParticles();
  useKeyboardNav(items);

  const visible = items.slice(0, budget);

  return (
    <>
      <SceneCamera />
      <SceneLights />
      <SceneControls autoRotate />
      <CubeWireframe />
      <AxisGrid />
      {visible.length > 0 && <AssetParticleCloud items={visible} />}
      {visible.length > 0 && <HudTooltip items={visible} />}
      <PostProcessing bloomIntensity={0.4} />
    </>
  );
}

export function QCubeScene() {
  const { data: items = [], isLoading, error } = useRanking();

  if (error) {
    return (
      <div className="scene-container">
        <div className="scene-error">
          <p>Erro ao carregar dados do ranking.</p>
          <p style={{ fontSize: 13, opacity: 0.6 }}>{String(error)}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="scene-container">
      <ScreenReaderDescription description="Visualização Q-Cube 3D: ativos financeiros posicionados por Earnings Yield, Return on Capital e Quality Score" />
      <SceneCanvas className="scene-canvas">
        <QCubeInner />
      </SceneCanvas>
      {items.length > 0 && new Set(items.map((it) => it.sector)).size > 1 && <HudLegend items={items} />}
      {isLoading && <div className="scene-loading-overlay">Carregando ranking...</div>}
    </div>
  );
}
