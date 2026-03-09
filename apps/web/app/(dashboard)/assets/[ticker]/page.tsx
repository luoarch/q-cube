'use client';

import Link from 'next/link';
import { use } from 'react';

import { useAssetDetail } from '../../../../src/hooks/api/useAssetDetail';

function formatPct(v: number | null | undefined): string {
  if (v == null) return '—';
  return `${(v * 100).toFixed(2)}%`;
}

function formatNumber(n: number | null | undefined): string {
  if (n == null) return '—';
  if (Math.abs(n) >= 1e9) return `R$ ${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `R$ ${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `R$ ${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(2);
}

function formatMultiple(v: number | null | undefined): string {
  if (v == null) return '—';
  return `${v.toFixed(2)}x`;
}

function MetricCard({ label, value, subtitle }: { label: string; value: string; subtitle?: string }) {
  return (
    <div
      style={{
        background: 'var(--bg-canvas)',
        border: '1px solid var(--border-color)',
        borderRadius: 8,
        padding: '0.75rem 1rem',
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'monospace', marginTop: 4 }}>
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

function QualityBadge({ score }: { score: number | null | undefined }) {
  if (score == null) return null;
  const label = score >= 0.7 ? 'HIGH' : score >= 0.4 ? 'MEDIUM' : 'LOW';
  const color = score >= 0.7 ? '#22c55e' : score >= 0.4 ? '#fbbf24' : '#ef4444';
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 700,
        padding: '3px 10px',
        borderRadius: 10,
        background: `${color}18`,
        color,
        letterSpacing: '0.5px',
      }}
    >
      {label}
    </span>
  );
}

export default function AssetDetailPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);
  const { data: asset, isLoading } = useAssetDetail(ticker);

  if (isLoading) {
    return (
      <div className="dashboard-page">
        <header className="dashboard-header">
          <Link href="/ranking" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
            ← Ranking
          </Link>
          <h1>{ticker}</h1>
        </header>
        <div style={{ padding: '2rem', color: 'var(--text-secondary)' }}>Carregando...</div>
      </div>
    );
  }

  if (!asset) {
    return (
      <div className="dashboard-page">
        <header className="dashboard-header">
          <Link href="/ranking" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
            ← Ranking
          </Link>
          <h1>{ticker}</h1>
        </header>
        <div style={{ padding: '2rem', color: 'var(--text-secondary)' }}>Ativo não encontrado.</div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <Link href="/ranking" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
          ← Ranking
        </Link>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ color: 'var(--accent-gold)' }}>{asset.ticker}</span>
          <span style={{ fontWeight: 400, fontSize: 16, color: 'var(--text-secondary)' }}>{asset.name}</span>
        </h1>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {asset.magicFormulaRank != null && (
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              Rank <strong style={{ color: 'var(--accent-gold)' }}>#{asset.magicFormulaRank}</strong>
            </span>
          )}
          <QualityBadge score={asset.compositeScore} />
        </div>
      </header>

      <div style={{ padding: '1.5rem', maxWidth: 1200, overflow: 'auto', flex: 1 }}>
        {/* Sector + price + links */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)', background: 'var(--bg-surface)', padding: '4px 12px', borderRadius: 6, border: '1px solid var(--border-color)' }}>
            {asset.sector}
          </span>
          {asset.price != null && (
            <span style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace' }}>
              R$ {asset.price.toFixed(2)}
            </span>
          )}
          <Link
            href={`/compare?tickers=${ticker}`}
            style={{ fontSize: 13, color: 'var(--text-secondary)', textDecoration: 'none', marginLeft: 'auto' }}
          >
            Comparar →
          </Link>
        </div>

        {/* Key metrics grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            gap: '0.75rem',
            marginBottom: '1.5rem',
          }}
        >
          <MetricCard label="Market Cap" value={formatNumber(asset.marketCap)} />
          <MetricCard label="P/L" value={asset.peRatio != null ? asset.peRatio.toFixed(1) : '—'} />
          <MetricCard label="P/VPA" value={asset.pbRatio != null ? asset.pbRatio.toFixed(2) : '—'} />
          <MetricCard label="Earnings Yield" value={formatPct(asset.earningsYield)} />
          <MetricCard label="ROIC" value={formatPct(asset.roic)} />
          <MetricCard label="ROE" value={formatPct(asset.roe)} />
          <MetricCard label="Margem Bruta" value={formatPct(asset.grossMargin)} />
          <MetricCard label="Margem Líquida" value={formatPct(asset.netMargin)} />
          <MetricCard label="Dívida Líq./EBITDA" value={formatMultiple(asset.netDebtToEbitda)} />
          <MetricCard label="Dividend Yield" value={formatPct(asset.dividendYield)} />
          {asset.compositeScore != null && (
            <MetricCard label="Composite Score" value={`${(asset.compositeScore * 100).toFixed(0)}%`} />
          )}
        </div>

        {/* Factor analysis */}
        {asset.factors && asset.factors.length > 0 && (
          <div
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: 8,
              padding: '1rem 1.25rem',
            }}
          >
            <h3 style={{ margin: '0 0 0.75rem', fontSize: 14, fontWeight: 600 }}>Factor Analysis</h3>
            {asset.factors.map((f) => (
              <FactorBar key={f.name} name={f.name} value={f.value} max={f.max} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
