'use client';

import dynamic from 'next/dynamic';
import { Suspense, type ReactNode } from 'react';

import { CanvasFallback } from './CanvasFallback';

const Canvas = dynamic(() => import('@react-three/fiber').then((m) => ({ default: m.Canvas })), {
  ssr: false,
});

export function SceneCanvas({
  children,
  className,
  frameloop = 'always',
}: {
  children: ReactNode;
  className?: string;
  frameloop?: 'always' | 'demand';
}) {
  return (
    <div className={className} style={{ width: '100%', height: '100%' }}>
      <Suspense fallback={<CanvasFallback />}>
        <Canvas
          frameloop={frameloop}
          gl={{ antialias: true, alpha: false }}
          dpr={[1, 2]}
          style={{ background: 'var(--bg-canvas, #0a0e1a)' }}
        >
          {children}
        </Canvas>
      </Suspense>
    </div>
  );
}
