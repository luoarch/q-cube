'use client';

import { useStrategyRun } from '../../../hooks/api/useStrategyRun';
import { SceneCamera } from '../core/SceneCamera';
import { SceneCanvas } from '../core/SceneCanvas';
import { SceneControls } from '../core/SceneControls';
import { SceneLights } from '../core/SceneLights';
import { AxisGrid } from '../objects/AxisGrid';
import { RibbonSurface } from '../objects/RibbonSurface';
import { HudMetricsCard } from '../ui/HudMetricsCard';
import { ScreenReaderDescription } from '../ui/ScreenReaderDescription';

function TimelineInner({ runId }: { runId: string }) {
  const { data: run } = useStrategyRun(runId);

  if (!run?.result) return null;

  return (
    <>
      <SceneCamera />
      <SceneLights />
      <SceneControls />
      <AxisGrid />
      <RibbonSurface curve={run.result.equityCurve} color="#4e79a7" />
    </>
  );
}

export function BacktestTimelineScene({ runId }: { runId: string | null }) {
  const { data: run, isLoading, error } = useStrategyRun(runId);

  if (!runId) {
    return (
      <div className="scene-container">
        <div className="scene-error">
          <p>Selecione um backtest para visualizar.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="scene-container">
        <div className="scene-error">
          <p>Erro ao carregar backtest.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="scene-container">
      <ScreenReaderDescription description="Backtest Timeline: curva de equity em 3D" />
      <SceneCanvas className="scene-canvas">
        <TimelineInner runId={runId} />
      </SceneCanvas>
      {run?.result?.metrics && <HudMetricsCard metrics={run.result.metrics} />}
      {isLoading && <div className="scene-loading-overlay">Carregando...</div>}
    </div>
  );
}
