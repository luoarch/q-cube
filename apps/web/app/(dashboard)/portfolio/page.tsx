'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';

import { usePortfolio } from '../../../src/hooks/api/usePortfolio';

const PortfolioConstellationScene = dynamic(
  () =>
    import('../../../src/components/three/scenes/PortfolioConstellationScene').then(
      (m) => m.PortfolioConstellationScene,
    ),
  { ssr: false },
);

function formatNumber(n: number): string {
  if (n === 0) return 'R$ 0';
  if (Math.abs(n) >= 1e12) return `R$ ${(n / 1e12).toFixed(1)}T`;
  if (Math.abs(n) >= 1e9) return `R$ ${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `R$ ${(n / 1e6).toFixed(0)}M`;
  return `R$ ${n.toFixed(0)}`;
}

function StatCard({ label, value, subtitle }: { label: string; value: string; subtitle?: string | undefined }) {
  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-color)',
        borderRadius: 8,
        padding: '1rem 1.25rem',
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, fontFamily: 'monospace', marginTop: 4, color: 'var(--accent-gold)' }}>
        {value}
      </div>
      {subtitle && (
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{subtitle}</div>
      )}
    </div>
  );
}

function FactorBar({ name, value, max }: { name: string; value: number; max: number }) {
  const pct = max > 0 ? Math.min(value / max, 1) : 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.25rem 0' }}>
      <div style={{ width: 120, fontSize: 13, color: 'var(--text-secondary)', flexShrink: 0 }}>{name}</div>
      <div style={{ flex: 1, height: 8, background: 'var(--grid-color)', borderRadius: 4, overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${pct * 100}%`,
            background: pct > 0.7 ? '#22c55e' : pct > 0.4 ? 'var(--accent-gold)' : '#ef4444',
            borderRadius: 4,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      <div style={{ width: 50, textAlign: 'right', fontSize: 12, fontFamily: 'monospace', color: 'var(--text-primary)' }}>
        {(pct * 100).toFixed(0)}%
      </div>
    </div>
  );
}

function returnColor(value: number): string {
  if (value > 0) return '#22c55e';
  if (value < 0) return '#ef4444';
  return 'var(--text-primary)';
}

export default function PortfolioPage() {
  const { data, isLoading, error } = usePortfolio();

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <h1>Portfolio</h1>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Top 10 holdings do ultimo ranking
        </span>
      </header>

      {isLoading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Carregando portfolio...
        </div>
      ) : error ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#ef4444' }}>
          Erro ao carregar portfolio.
        </div>
      ) : !data || data.holdings.length === 0 ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          <p>Nenhum portfolio disponivel. Execute uma estrategia primeiro.</p>
          <Link
            href="/strategy"
            style={{
              color: 'var(--accent-gold)',
              textDecoration: 'none',
              fontWeight: 600,
              fontSize: 13,
            }}
          >
            Ir para Strategy →
          </Link>
        </div>
      ) : (
        <div style={{ overflow: 'auto', flex: 1 }}>
          <div style={{ padding: '1.25rem' }}>
            {/* Stat Cards */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: '0.75rem',
                marginBottom: '1.5rem',
              }}
            >
              <StatCard label="Valor Total" value={formatNumber(data.totalValue)} />
              <StatCard label="Retorno Medio (ROIC)" value={`${data.totalReturn.toFixed(2)}%`} />
              <StatCard label="Holdings" value={String(data.holdings.length)} subtitle="equal-weight" />
            </div>

            {/* Holdings Table */}
            <div
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: 8,
                overflow: 'hidden',
                marginBottom: '1.5rem',
              }}
            >
              <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)' }}>
                <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Holdings</h3>
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Ticker</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Empresa</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Setor</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Peso</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Valor</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Retorno</th>
                  </tr>
                </thead>
                <tbody>
                  {data.holdings.map((h) => (
                    <tr key={h.ticker}>
                      <td style={{ padding: '8px 12px' }}>
                        <Link
                          href={`/assets/${h.ticker}`}
                          style={{ color: 'var(--accent-gold)', textDecoration: 'none', fontWeight: 600 }}
                        >
                          {h.ticker}
                        </Link>
                      </td>
                      <td style={{ padding: '8px 12px', color: 'var(--text-secondary)', fontSize: 13, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {h.name}
                      </td>
                      <td style={{ padding: '8px 12px', fontSize: 12, color: 'var(--text-secondary)' }}>
                        {h.sector}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
                        {h.weight.toFixed(1)}%
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
                        {formatNumber(h.value)}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontSize: 13, color: returnColor(h.return) }}>
                        {h.return.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Factor Tilt */}
            {data.factorTilt.length > 0 && (
              <div
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 8,
                  padding: '1rem 1.25rem',
                  marginBottom: '1.5rem',
                }}
              >
                <h3 style={{ margin: '0 0 0.75rem', fontSize: 14, fontWeight: 600 }}>Factor Tilt</h3>
                {data.factorTilt.map((f) => (
                  <FactorBar key={f.name} name={f.name} value={f.value} max={f.max} />
                ))}
              </div>
            )}
          </div>

          {/* 3D Constellation Scene */}
          <div
            style={{
              height: 400,
              borderTop: '1px solid var(--border-color)',
            }}
          >
            <PortfolioConstellationScene />
          </div>
        </div>
      )}
    </div>
  );
}
