'use client';

export function ScreenReaderDescription({ description }: { description: string }) {
  return (
    <>
      <div
        id="scene-live-region"
        role="status"
        aria-live="polite"
        style={{
          position: 'absolute',
          width: 1,
          height: 1,
          overflow: 'hidden',
          clip: 'rect(0 0 0 0)',
          whiteSpace: 'nowrap',
        }}
      />
      <div
        role="img"
        aria-label={description}
        style={{
          position: 'absolute',
          width: 1,
          height: 1,
          overflow: 'hidden',
          clip: 'rect(0 0 0 0)',
          whiteSpace: 'nowrap',
        }}
      />
    </>
  );
}
