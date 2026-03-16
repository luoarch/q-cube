'use client';

import Link from 'next/link';
import { use } from 'react';

import { useAssetDetail } from '../../../../src/hooks/api/useAssetDetail';
import { useThesisBreakdown } from '../../../../src/hooks/api/useThesisBreakdown';

import type { Plan2BreakdownResponse, DimensionBreakdownItem, ThesisBucket, EvidenceQuality, ScoreSourceType } from '@q3/shared-contracts';

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

// ---------------------------------------------------------------------------
// Thesis Breakdown components
// ---------------------------------------------------------------------------

const BUCKET_COLORS: Record<ThesisBucket, string> = {
  A_DIRECT: '#22c55e',
  B_INDIRECT: '#3b82f6',
  C_NEUTRAL: '#94a3b8',
  D_FRAGILE: '#ef4444',
};

const BUCKET_LABELS: Record<ThesisBucket, string> = {
  A_DIRECT: 'A Direct',
  B_INDIRECT: 'B Indirect',
  C_NEUTRAL: 'C Neutral',
  D_FRAGILE: 'D Fragile',
};

const EVIDENCE_COLORS: Record<EvidenceQuality, string> = {
  HIGH_EVIDENCE: '#22c55e',
  MIXED_EVIDENCE: '#fbbf24',
  LOW_EVIDENCE: '#ef4444',
};

const SOURCE_COLORS: Record<ScoreSourceType, string> = {
  QUANTITATIVE: '#22c55e',
  SECTOR_PROXY: '#3b82f6',
  RUBRIC_MANUAL: '#a855f7',
  AI_ASSISTED: '#8b5cf6',
  DERIVED: '#fbbf24',
  DEFAULT: '#ef4444',
};

function SourceChip({ type, showWarning }: { type: ScoreSourceType; showWarning: boolean }) {
  const color = SOURCE_COLORS[type];
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '1px 6px',
        borderRadius: 6,
        background: `${color}14`,
        color,
        letterSpacing: '0.02em',
      }}
      title={showWarning ? 'Score derivado de valor padrão — não reflete dados reais do emissor' : undefined}
    >
      {type}{showWarning ? ' *' : ''}
    </span>
  );
}

function DimensionRow({ dim }: { dim: DimensionBreakdownItem }) {
  const barPct = Math.min(dim.score / 100, 1);
  const barColor = dim.isDefault || dim.isDerived
    ? '#64748b'
    : barPct > 0.6 ? '#22c55e' : barPct > 0.3 ? 'var(--accent-gold)' : '#ef4444';

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 60px 60px 60px auto',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.4rem 0',
        borderBottom: '1px solid var(--border-color)',
        opacity: dim.isDefault || dim.isDerived ? 0.7 : 1,
      }}
    >
      <div>
        <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>{dim.label}</div>
        {dim.evidenceRef && (
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{dim.evidenceRef}</div>
        )}
      </div>
      <div style={{ fontFamily: 'monospace', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>
        {dim.score.toFixed(1)}
      </div>
      <div style={{ fontFamily: 'monospace', fontSize: 12, textAlign: 'right', color: 'var(--text-secondary)' }}>
        x{dim.weight.toFixed(2)}
      </div>
      <div style={{ fontFamily: 'monospace', fontSize: 12, textAlign: 'right', color: 'var(--text-secondary)' }}>
        ={dim.weightedContribution.toFixed(1)}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <div style={{ width: 60, height: 6, background: 'var(--grid-color)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${barPct * 100}%`, background: barColor, borderRadius: 3 }} />
        </div>
        <SourceChip type={dim.sourceType} showWarning={dim.isDefault || dim.isDerived} />
      </div>
    </div>
  );
}

function ThesisBreakdownSection({ breakdown }: { breakdown: Plan2BreakdownResponse }) {
  const bucketColor = BUCKET_COLORS[breakdown.bucket];
  const evidenceColor = EVIDENCE_COLORS[breakdown.evidenceQuality];

  const hasDefaultWarning = [
    ...breakdown.opportunityDimensions,
    ...breakdown.fragilityDimensions,
  ].some((d) => d.isDefault || d.isDerived);

  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-color)',
        borderRadius: 8,
        padding: '1rem 1.25rem',
        marginTop: '1rem',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Thesis Breakdown</h3>
        <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10, background: `${bucketColor}18`, color: bucketColor }}>
          {BUCKET_LABELS[breakdown.bucket]}
        </span>
        <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10, background: `${evidenceColor}14`, color: evidenceColor }}>
          {breakdown.evidenceQuality.replace('_', ' ')}
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 'auto' }}>
          Rank #{breakdown.thesisRank} | Score {breakdown.thesisRankScore.toFixed(1)}
        </span>
      </div>

      {/* Score summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '1rem' }}>
        <div style={{ background: 'var(--bg-canvas)', border: '1px solid var(--border-color)', borderRadius: 6, padding: '0.5rem 0.75rem', textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Commodity Affinity</div>
          <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace', color: '#22c55e' }}>{breakdown.finalCommodityAffinityScore.toFixed(1)}</div>
        </div>
        <div style={{ background: 'var(--bg-canvas)', border: '1px solid var(--border-color)', borderRadius: 6, padding: '0.5rem 0.75rem', textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Dollar Fragility</div>
          <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace', color: '#fbbf24' }}>{breakdown.finalDollarFragilityScore.toFixed(1)}</div>
        </div>
        <div style={{ background: 'var(--bg-canvas)', border: '1px solid var(--border-color)', borderRadius: 6, padding: '0.5rem 0.75rem', textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Core Base</div>
          <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace', color: 'var(--text-primary)' }}>{breakdown.baseCoreScore.toFixed(1)}</div>
        </div>
      </div>

      {/* Opportunity vector */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.4rem', letterSpacing: '0.5px' }}>
          Opportunity Vector
        </div>
        {breakdown.opportunityDimensions.map((dim) => (
          <DimensionRow key={dim.key} dim={dim} />
        ))}
      </div>

      {/* Fragility vector */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.4rem', letterSpacing: '0.5px' }}>
          Fragility Vector
        </div>
        {breakdown.fragilityDimensions.map((dim) => (
          <DimensionRow key={dim.key} dim={dim} />
        ))}
      </div>

      {/* Default/Derived warning */}
      {hasDefaultWarning && (
        <div style={{ fontSize: 11, color: '#ef4444', padding: '0.4rem 0.6rem', background: 'rgba(239,68,68,0.06)', borderRadius: 6, marginBottom: '0.75rem' }}>
          * Dimensões marcadas DEFAULT ou DERIVED usam valores padrão — não refletem dados reais do emissor.
          A precisão dessas dimensões é limitada no MVP.
        </div>
      )}

      {/* Explanation */}
      {(breakdown.positives.length > 0 || breakdown.negatives.length > 0) && (
        <div style={{ marginBottom: '0.75rem' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.4rem', letterSpacing: '0.5px' }}>
            Rationale
          </div>
          {breakdown.positives.length > 0 && (
            <ul style={{ margin: '0.25rem 0', paddingLeft: '1.25rem' }}>
              {breakdown.positives.map((p, i) => (
                <li key={i} style={{ fontSize: 12, color: '#22c55e', marginBottom: 2 }}>{p}</li>
              ))}
            </ul>
          )}
          {breakdown.negatives.length > 0 && (
            <ul style={{ margin: '0.25rem 0', paddingLeft: '1.25rem' }}>
              {breakdown.negatives.map((n, i) => (
                <li key={i} style={{ fontSize: 12, color: '#ef4444', marginBottom: 2 }}>{n}</li>
              ))}
            </ul>
          )}
          {breakdown.summary && (
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: '0.4rem', fontStyle: 'italic' }}>
              {breakdown.summary}
            </div>
          )}
        </div>
      )}

      {/* Run context footer */}
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', opacity: 0.7, display: 'flex', gap: '1rem', flexWrap: 'wrap', borderTop: '1px solid var(--border-color)', paddingTop: '0.5rem' }}>
        <span>as_of: {breakdown.asOfDate}</span>
        <span>run: {breakdown.runId.slice(0, 8)}</span>
        <span>config: {breakdown.thesisConfigVersion}</span>
        <span>pipeline: {breakdown.pipelineVersion}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AssetDetailPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);
  const { data: asset, isLoading } = useAssetDetail(ticker);
  const { data: breakdown } = useThesisBreakdown(ticker);

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

        {/* Thesis Breakdown */}
        {breakdown && <ThesisBreakdownSection breakdown={breakdown} />}
      </div>
    </div>
  );
}
