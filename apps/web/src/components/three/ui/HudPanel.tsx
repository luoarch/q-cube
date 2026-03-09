'use client';

import Link from 'next/link';

import { useAssetDetail } from '../../../hooks/api/useAssetDetail';
import { useSceneStore } from '../../../stores/sceneStore';

export function HudPanel({ ticker }: { ticker: string }) {
  const { data: asset, isLoading } = useAssetDetail(ticker);
  const select = useSceneStore((s) => s.select);

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        width: 320,
        height: '100%',
        background: 'rgba(10, 14, 26, 0.95)',
        borderLeft: '1px solid var(--border-color, rgba(148,163,184,0.15))',
        color: 'var(--text-primary, #e2e8f0)',
        padding: '1.5rem',
        fontFamily: 'IBM Plex Sans, sans-serif',
        overflowY: 'auto',
        zIndex: 20,
        backdropFilter: 'blur(12px)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1rem',
        }}
      >
        <h2 style={{ margin: 0, fontSize: '1.25rem' }}>{ticker}</h2>
        <button
          onClick={() => select(null)}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-secondary, #94a3b8)',
            fontSize: 18,
            cursor: 'pointer',
          }}
        >
          ✕
        </button>
      </div>

      {isLoading && <p style={{ color: 'var(--text-secondary)' }}>Carregando...</p>}

      {asset && (
        <>
          <p style={{ margin: '0 0 0.5rem', color: 'var(--text-secondary)', fontSize: 14 }}>
            {asset.name} · {asset.sector}
          </p>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '0.75rem',
              marginTop: '1rem',
            }}
          >
            <MetricCard
              label="Earnings Yield"
              value={`${(asset.earningsYield * 100).toFixed(1)}%`}
            />
            <MetricCard label="ROC" value={`${(asset.returnOnCapital * 100).toFixed(1)}%`} />
            <MetricCard label="ROIC" value={`${(asset.roic * 100).toFixed(1)}%`} />
            <MetricCard label="Margem Líquida" value={`${(asset.netMargin * 100).toFixed(1)}%`} />
            <MetricCard label="Margem Bruta" value={`${(asset.grossMargin * 100).toFixed(1)}%`} />
            <MetricCard label="Dív. Líq./EBITDA" value={asset.netDebtToEbitda.toFixed(2)} />
            {asset.compositeScore !== null && (
              <MetricCard
                label="Score Composto"
                value={`${(asset.compositeScore * 100).toFixed(0)}%`}
              />
            )}
          </div>

          <div style={{ display: 'flex', gap: 6, marginTop: '1rem' }}>
            <Link
              href={`/intelligence/${ticker}`}
              style={{
                flex: 1,
                textAlign: 'center',
                fontSize: 12,
                padding: '6px 8px',
                background: 'rgba(148,163,184,0.08)',
                border: '1px solid rgba(148,163,184,0.2)',
                borderRadius: 6,
                color: 'var(--text-primary, #e2e8f0)',
                textDecoration: 'none',
              }}
            >
              Inteligencia
            </Link>
            <Link
              href={`/chat?ticker=${ticker}`}
              style={{
                flex: 1,
                textAlign: 'center',
                fontSize: 12,
                padding: '6px 8px',
                background: 'rgba(251,191,36,0.1)',
                border: '1px solid rgba(251,191,36,0.3)',
                borderRadius: 6,
                color: 'var(--accent-gold, #fbbf24)',
                textDecoration: 'none',
                fontWeight: 600,
              }}
            >
              Analisar com AI
            </Link>
          </div>

          {asset.factors.length > 0 && (
            <div style={{ marginTop: '1.5rem' }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: '0.5rem' }}>
                Fatores (percentil)
              </h3>
              {asset.factors.map((f) => (
                <div key={f.name} style={{ marginBottom: 6 }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: 12,
                      marginBottom: 2,
                    }}
                  >
                    <span>{f.name}</span>
                    <span>{(f.value * 100).toFixed(0)}%</span>
                  </div>
                  <div style={{ height: 4, background: 'rgba(148,163,184,0.15)', borderRadius: 2 }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${f.value * 100}%`,
                        background: 'var(--accent-gold, #fbbf24)',
                        borderRadius: 2,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        background: 'rgba(148, 163, 184, 0.06)',
        padding: '0.5rem 0.75rem',
        borderRadius: 8,
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 600 }}>{value}</div>
    </div>
  );
}
