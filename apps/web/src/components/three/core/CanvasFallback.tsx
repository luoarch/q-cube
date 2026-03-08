'use client';

export function CanvasFallback() {
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-canvas, #0a0e1a)',
        color: 'var(--text-primary, #e2e8f0)',
        fontFamily: 'IBM Plex Sans, sans-serif',
      }}
    >
      <div style={{ textAlign: 'center' }}>
        <div
          style={{
            width: 40,
            height: 40,
            border: '3px solid var(--grid-color, rgba(148,163,184,0.08))',
            borderTopColor: 'var(--accent-gold, #fbbf24)',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 1rem',
          }}
        />
        <p style={{ margin: 0, opacity: 0.6 }}>Carregando visualização 3D...</p>
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </div>
    </div>
  );
}

export function WebGLNotSupported() {
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-canvas, #0a0e1a)',
        color: 'var(--text-primary, #e2e8f0)',
        padding: '2rem',
        textAlign: 'center',
      }}
    >
      <p>WebGL não suportado neste navegador.</p>
    </div>
  );
}
