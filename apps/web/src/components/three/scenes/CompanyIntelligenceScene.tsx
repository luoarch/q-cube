'use client';

import { Text, PerspectiveCamera } from '@react-three/drei';

import { useIntelligence } from '../../../hooks/api/useIntelligence';
import { SceneCanvas } from '../core/SceneCanvas';
import { SceneControls } from '../core/SceneControls';
import { SceneLights } from '../core/SceneLights';
import { ScreenReaderDescription } from '../ui/ScreenReaderDescription';

const BLOCK_LABELS = ['Earnings Quality', 'Safety', 'Consistency', 'Capital Disc.'];
const BLOCK_COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#a78bfa'];

function ScoreBar({
  position,
  score,
  color,
  label,
}: {
  position: [number, number, number];
  score: number;
  color: string;
  label: string;
}) {
  const height = Math.max(0.05, score * 3);
  return (
    <group position={position}>
      {/* Base bar (ghost) */}
      <mesh position={[0, 1.5, 0]}>
        <boxGeometry args={[0.6, 3, 0.6]} />
        <meshStandardMaterial color="#94a3b8" transparent opacity={0.06} />
      </mesh>
      {/* Score bar */}
      <mesh position={[0, height / 2, 0]}>
        <boxGeometry args={[0.6, height, 0.6]} />
        <meshStandardMaterial color={color} transparent opacity={0.85} />
      </mesh>
      {/* Label */}
      <Text position={[0, -0.4, 0]} fontSize={0.14} color="#94a3b8" anchorX="center">
        {label}
      </Text>
      {/* Value */}
      <Text
        position={[0, height + 0.25, 0]}
        fontSize={0.18}
        color={color}
        anchorX="center"
        fontWeight={700}
      >
        {(score * 100).toFixed(0)}
      </Text>
    </group>
  );
}

function FlagBadge({
  position,
  text,
  type,
}: {
  position: [number, number, number];
  text: string;
  type: 'red' | 'strength';
}) {
  return (
    <Text
      position={position}
      fontSize={0.1}
      color={type === 'red' ? '#f87171' : '#34d399'}
      anchorX="left"
      maxWidth={4}
    >
      {type === 'red' ? '● ' : '◆ '}
      {text.replace(/_/g, ' ')}
    </Text>
  );
}

function IntelligenceInner({ ticker }: { ticker: string }) {
  const { data } = useIntelligence(ticker);

  if (!data) return null;

  const scores = data.refiner;
  const flags = data.flags;

  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 2, 8]} fov={45} />
      <SceneLights />
      <SceneControls />

      {/* Refiner score bars */}
      {scores && (
        <group position={[-2.25, 0, 0]}>
          <ScoreBar
            position={[0, 0, 0]}
            score={scores.earningsQualityScore ?? 0}
            color={BLOCK_COLORS[0]!}
            label={BLOCK_LABELS[0]!}
          />
          <ScoreBar
            position={[1.5, 0, 0]}
            score={scores.safetyScore ?? 0}
            color={BLOCK_COLORS[1]!}
            label={BLOCK_LABELS[1]!}
          />
          <ScoreBar
            position={[3, 0, 0]}
            score={scores.operatingConsistencyScore ?? 0}
            color={BLOCK_COLORS[2]!}
            label={BLOCK_LABELS[2]!}
          />
          <ScoreBar
            position={[4.5, 0, 0]}
            score={scores.capitalDisciplineScore ?? 0}
            color={BLOCK_COLORS[3]!}
            label={BLOCK_LABELS[3]!}
          />
        </group>
      )}

      {/* Composite score */}
      {scores?.refinementScore != null && (
        <Text position={[0, 3.8, 0]} fontSize={0.22} color="#fbbf24" anchorX="center">
          Refinement Score: {(scores.refinementScore * 100).toFixed(0)}%
        </Text>
      )}

      {/* Flags column */}
      {flags && (
        <group position={[-4, 2.5, 0]}>
          {flags.red.slice(0, 5).map((f, i) => (
            <FlagBadge key={f} position={[0, -i * 0.25, 0]} text={f} type="red" />
          ))}
          {flags.strength.slice(0, 5).map((f, i) => (
            <FlagBadge
              key={f}
              position={[0, -(flags.red.length + i) * 0.25 - 0.3, 0]}
              text={f}
              type="strength"
            />
          ))}
        </group>
      )}

      {/* No refiner data placeholder */}
      {!scores && (
        <Text position={[0, 1.5, 0]} fontSize={0.2} color="#94a3b8" anchorX="center">
          Refiner data unavailable — run a strategy first
        </Text>
      )}
    </>
  );
}

export function CompanyIntelligenceScene({ ticker }: { ticker: string }) {
  const { isLoading, error } = useIntelligence(ticker);

  if (error) {
    return (
      <div className="scene-container">
        <div className="scene-error">
          <p>Dados não encontrados: {ticker}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="scene-container">
      <ScreenReaderDescription
        description={`Painel de inteligência da empresa ${ticker} com scores do refiner e flags`}
      />
      <SceneCanvas className="scene-canvas" frameloop="demand">
        <IntelligenceInner ticker={ticker} />
      </SceneCanvas>
      {isLoading && <div className="scene-loading-overlay">Carregando...</div>}
    </div>
  );
}
