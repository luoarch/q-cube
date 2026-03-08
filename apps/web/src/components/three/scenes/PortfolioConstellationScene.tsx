'use client';

import { Text } from '@react-three/drei';
import { useMemo } from 'react';

import { usePortfolio } from '../../../hooks/api/usePortfolio';
import { getSectorColor } from '../../../lib/three/colorMap';
import { SceneCamera } from '../core/SceneCamera';
import { SceneCanvas } from '../core/SceneCanvas';
import { SceneControls } from '../core/SceneControls';
import { SceneLights } from '../core/SceneLights';
import { AssetParticle } from '../objects/AssetParticle';
import { ConnectionLine } from '../objects/ConnectionLine';
import { ScreenReaderDescription } from '../ui/ScreenReaderDescription';

function ConstellationInner() {
  const { data: portfolio } = usePortfolio();

  const layout = useMemo(() => {
    if (!portfolio?.holdings.length) return [];
    const n = portfolio.holdings.length;
    return portfolio.holdings.map((h, i) => {
      const angle = (i / n) * Math.PI * 2;
      const r = 2 + h.weight * 5;
      return {
        ...h,
        position: [Math.cos(angle) * r, (Math.random() - 0.5) * 2, Math.sin(angle) * r] as [
          number,
          number,
          number,
        ],
      };
    });
  }, [portfolio?.holdings]);

  const connections = useMemo(() => {
    const conns: Array<{
      start: [number, number, number];
      end: [number, number, number];
      color: string;
    }> = [];
    for (let i = 0; i < layout.length; i++) {
      for (let j = i + 1; j < layout.length; j++) {
        if (layout[i]!.sector === layout[j]!.sector) {
          conns.push({
            start: layout[i]!.position,
            end: layout[j]!.position,
            color: getSectorColor(layout[i]!.sector),
          });
        }
      }
    }
    return conns;
  }, [layout]);

  if (!portfolio) return null;

  return (
    <>
      <SceneCamera />
      <SceneLights />
      <SceneControls autoRotate />

      {layout.map((h) => (
        <group key={h.ticker} position={h.position}>
          <AssetParticle
            position={[0, 0, 0]}
            radius={0.05 + h.weight * 0.5}
            color={getSectorColor(h.sector)}
          />
          <Text
            position={[0, 0.05 + h.weight * 0.5 + 0.15, 0]}
            fontSize={0.12}
            color="#e2e8f0"
            anchorX="center"
          >
            {h.ticker}
          </Text>
        </group>
      ))}

      {connections.map((c, i) => (
        <ConnectionLine key={i} start={c.start} end={c.end} color={c.color} />
      ))}
    </>
  );
}

export function PortfolioConstellationScene() {
  const { isLoading, error } = usePortfolio();

  if (error) {
    return (
      <div className="scene-container">
        <div className="scene-error">
          <p>Erro ao carregar portfolio.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="scene-container">
      <ScreenReaderDescription description="Portfolio Constellation: holdings como nós conectados por setor" />
      <SceneCanvas className="scene-canvas">
        <ConstellationInner />
      </SceneCanvas>
      {isLoading && <div className="scene-loading-overlay">Carregando...</div>}
    </div>
  );
}
