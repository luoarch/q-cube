'use client';

import { EffectComposer, DepthOfField, ToneMapping } from '@react-three/postprocessing';
import { ToneMappingMode } from 'postprocessing';

export function DepthOfFieldPreset({
  focusDistance = 0.02,
  focalLength = 0.5,
  bokehScale = 3,
}: {
  focusDistance?: number;
  focalLength?: number;
  bokehScale?: number;
}) {
  return (
    <EffectComposer>
      <DepthOfField
        focusDistance={focusDistance}
        focalLength={focalLength}
        bokehScale={bokehScale}
      />
      <ToneMapping mode={ToneMappingMode.AGX} />
    </EffectComposer>
  );
}
