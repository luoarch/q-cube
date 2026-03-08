'use client';

import { useMemo } from 'react';

import { useRanking } from '../../../hooks/api/useRanking';
import { useSceneStore } from '../../../stores/sceneStore';
import { PostProcessing } from '../core/PostProcessing';
import { SceneCamera } from '../core/SceneCamera';
import { SceneCanvas } from '../core/SceneCanvas';
import { SceneControls } from '../core/SceneControls';
import { SceneLights } from '../core/SceneLights';
import { useKeyboardNav } from '../hooks/useKeyboardNav';
import { useResponsiveParticles } from '../hooks/useResponsiveParticles';
import { AssetParticleCloud } from '../objects/AssetParticleCloud';
import { AxisGrid } from '../objects/AxisGrid';
import { HudFilterBar } from '../ui/HudFilterBar';
import { HudLegend } from '../ui/HudLegend';
import { HudPanel } from '../ui/HudPanel';
import { HudTooltip } from '../ui/HudTooltip';
import { ScreenReaderDescription } from '../ui/ScreenReaderDescription';

function GalaxyInner() {
  const { data: items = [] } = useRanking();
  const budget = useResponsiveParticles();
  const filters = useSceneStore((s) => s.filters);
  useKeyboardNav(items);

  const filtered = useMemo(() => {
    let result = items;
    if (filters.sector) result = result.filter((it) => it.sector === filters.sector);
    if (filters.quality) result = result.filter((it) => it.quality === filters.quality);
    if (filters.liquidity) result = result.filter((it) => it.liquidity === filters.liquidity);
    return result.slice(0, budget);
  }, [items, filters, budget]);

  return (
    <>
      <SceneCamera />
      <SceneLights />
      <SceneControls />
      <AxisGrid />
      {filtered.length > 0 && <AssetParticleCloud items={filtered} />}
      {filtered.length > 0 && <HudTooltip items={filtered} />}
      <PostProcessing bloomIntensity={0.6} />
    </>
  );
}

export function RankingGalaxyScene() {
  const { data: items = [], isLoading, error } = useRanking();
  const selectedTicker = useSceneStore((s) => s.selectedTicker);

  if (error) {
    return (
      <div className="scene-container">
        <div className="scene-error">
          <p>Erro ao carregar ranking.</p>
        </div>
      </div>
    );
  }

  const sectors = [...new Set(items.map((it) => it.sector))].sort();

  return (
    <div className="scene-container">
      <ScreenReaderDescription description="Ranking Galaxy: ativos em 3D por Earnings Yield, Return on Capital e Market Cap" />
      <SceneCanvas className="scene-canvas">
        <GalaxyInner />
      </SceneCanvas>
      {items.length > 0 && <HudLegend items={items} />}
      <HudFilterBar sectors={sectors} />
      {selectedTicker && <HudPanel ticker={selectedTicker} />}
      {isLoading && <div className="scene-loading-overlay">Carregando...</div>}
    </div>
  );
}
