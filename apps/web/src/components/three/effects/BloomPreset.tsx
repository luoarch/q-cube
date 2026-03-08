'use client';

import { EffectComposer, Bloom, ToneMapping } from '@react-three/postprocessing';
import { ToneMappingMode } from 'postprocessing';

export function BloomPreset({
  intensity = 0.4,
  threshold = 0.9,
}: {
  intensity?: number;
  threshold?: number;
}) {
  return (
    <EffectComposer>
      <Bloom
        luminanceThreshold={threshold}
        luminanceSmoothing={0.025}
        intensity={intensity}
        mipmapBlur
      />
      <ToneMapping mode={ToneMappingMode.AGX} />
    </EffectComposer>
  );
}
