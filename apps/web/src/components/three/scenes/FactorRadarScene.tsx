'use client';

import { Text, PerspectiveCamera } from '@react-three/drei';

import { useAssetDetail } from '../../../hooks/api/useAssetDetail';
import { SceneCanvas } from '../core/SceneCanvas';
import { SceneControls } from '../core/SceneControls';
import { SceneLights } from '../core/SceneLights';
import { RadarPolyhedron } from '../objects/RadarPolyhedron';
import { ScreenReaderDescription } from '../ui/ScreenReaderDescription';

const FACTOR_LABELS = ['ROIC', 'EY', 'ROC', 'Net Margin', 'Gross Margin'];
const ANGLE_STEP = (Math.PI * 2) / 5;
const LABEL_R = 2.4;

function RadarInner({ ticker }: { ticker: string }) {
  const { data: asset } = useAssetDetail(ticker);

  if (!asset) return null;

  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 0, 6]} fov={50} />
      <SceneLights />
      <SceneControls />

      {/* Axis labels */}
      {FACTOR_LABELS.map((label, i) => {
        const angle = i * ANGLE_STEP - Math.PI / 2;
        return (
          <Text
            key={label}
            position={[Math.cos(angle) * LABEL_R, Math.sin(angle) * LABEL_R, 0]}
            fontSize={0.15}
            color="#94a3b8"
            anchorX="center"
          >
            {label}
          </Text>
        );
      })}

      {/* Reference circles */}
      {[0.25, 0.5, 0.75, 1].map((r) => (
        <mesh key={r} rotation={[0, 0, 0]}>
          <ringGeometry args={[r * 2 - 0.01, r * 2, 64]} />
          <meshBasicMaterial color="#94a3b8" transparent opacity={0.08} side={2} />
        </mesh>
      ))}

      <RadarPolyhedron asset={asset} />
    </>
  );
}

export function FactorRadarScene({ ticker }: { ticker: string }) {
  const { isLoading, error } = useAssetDetail(ticker);

  if (error) {
    return (
      <div className="scene-container">
        <div className="scene-error">
          <p>Ativo não encontrado: {ticker}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="scene-container">
      <ScreenReaderDescription description={`Radar de fatores do ativo ${ticker}`} />
      <SceneCanvas className="scene-canvas" frameloop="demand">
        <RadarInner ticker={ticker} />
      </SceneCanvas>
      {isLoading && <div className="scene-loading-overlay">Carregando...</div>}
    </div>
  );
}
