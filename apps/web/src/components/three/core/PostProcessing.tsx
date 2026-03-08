'use client';

import { EffectComposer, Bloom, ToneMapping } from '@react-three/postprocessing';
import { ToneMappingMode } from 'postprocessing';

export function PostProcessing({
  bloomIntensity = 0.4,
  enabled = true,
}: {
  bloomIntensity?: number;
  enabled?: boolean;
}) {
  if (!enabled) return null;

  return (
    <EffectComposer>
      <Bloom
        luminanceThreshold={0.9}
        luminanceSmoothing={0.025}
        intensity={bloomIntensity}
        mipmapBlur
      />
      <ToneMapping mode={ToneMappingMode.AGX} />
    </EffectComposer>
  );
}
