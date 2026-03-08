'use client';

import { useIntelligence } from '../../../hooks/api/useIntelligence';

import type { CompanyIntelligence } from '@q3/shared-contracts';

const PANEL: React.CSSProperties = {
  position: 'absolute',
  top: 0,
  right: 0,
  width: 340,
  height: '100%',
  background: 'rgba(10, 14, 26, 0.95)',
  borderLeft: '1px solid var(--border-color, rgba(148,163,184,0.15))',
  color: 'var(--text-primary, #e2e8f0)',
  padding: '1.5rem',
  fontFamily: 'IBM Plex Sans, sans-serif',
  overflowY: 'auto',
  zIndex: 20,
  backdropFilter: 'blur(12px)',
};

const SECTION: React.CSSProperties = { marginTop: '1.25rem' };
const SECTION_TITLE: React.CSSProperties = { fontSize: 13, fontWeight: 600, marginBottom: '0.5rem', color: 'var(--accent-gold, #fbbf24)' };
const GRID: React.CSSProperties = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' };

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: 'rgba(148,163,184,0.06)', padding: '0.5rem 0.75rem', borderRadius: 8 }}>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 600 }}>{value}</div>
    </div>
  );
}

function Badge({ text, variant }: { text: string; variant: 'red' | 'green' | 'yellow' | 'gray' }) {
  const colors = {
    red: { bg: 'rgba(239,68,68,0.15)', fg: '#f87171' },
    green: { bg: 'rgba(52,211,153,0.15)', fg: '#34d399' },
    yellow: { bg: 'rgba(251,191,36,0.15)', fg: '#fbbf24' },
    gray: { bg: 'rgba(148,163,184,0.1)', fg: '#94a3b8' },
  };
  const c = colors[variant];
  return (
    <span style={{
      display: 'inline-block',
      background: c.bg,
      color: c.fg,
      fontSize: 11,
      padding: '2px 8px',
      borderRadius: 4,
      marginRight: 4,
      marginBottom: 4,
    }}>
      {text.replace(/_/g, ' ')}
    </span>
  );
}

function ReliabilityDot({ level }: { level: string }) {
  const color = level === 'high' ? '#34d399' : level === 'medium' ? '#fbbf24' : level === 'low' ? '#fb923c' : '#64748b';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, display: 'inline-block' }} />
      {level}
    </span>
  );
}

function TrendMini({ values }: { values: { referenceDate: string; value: number | null }[] }) {
  if (values.length === 0) return <span style={{ color: '#64748b', fontSize: 12 }}>—</span>;
  return (
    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
      {values.map((v, i) => (
        <span key={v.referenceDate}>
          {v.value != null ? v.value.toFixed(2) : '—'}
          {i < values.length - 1 ? ' → ' : ''}
        </span>
      ))}
    </span>
  );
}

export function IntelligencePanel({ ticker }: { ticker: string }) {
  const { data, isLoading } = useIntelligence(ticker);

  return (
    <div style={PANEL}>
      <h2 style={{ margin: 0, fontSize: '1.25rem' }}>{ticker}</h2>

      {isLoading && <p style={{ color: 'var(--text-secondary)', marginTop: 8 }}>Carregando...</p>}

      {data && (
        <>
          {/* Header */}
          <p style={{ margin: '0.25rem 0 0', color: 'var(--text-secondary)', fontSize: 13 }}>
            {data.baseDetail.name} · {data.baseDetail.sector}
          </p>
          <div style={{ display: 'flex', gap: 8, marginTop: 6, alignItems: 'center' }}>
            {data.classification && <Badge text={data.classification} variant="gray" />}
            {data.scoreReliability && <ReliabilityDot level={data.scoreReliability} />}
          </div>

          {/* Base metrics */}
          <div style={SECTION}>
            <div style={SECTION_TITLE}>Fundamentals</div>
            <div style={GRID}>
              <MetricCard label="Earnings Yield" value={`${(data.baseDetail.earningsYield * 100).toFixed(1)}%`} />
              <MetricCard label="ROIC" value={`${(data.baseDetail.roic * 100).toFixed(1)}%`} />
              <MetricCard label="Margem Bruta" value={`${(data.baseDetail.grossMargin * 100).toFixed(1)}%`} />
              <MetricCard label="Margem Líquida" value={`${(data.baseDetail.netMargin * 100).toFixed(1)}%`} />
              <MetricCard label="Dív./EBITDA" value={data.baseDetail.netDebtToEbitda.toFixed(2)} />
              {data.baseDetail.compositeScore != null && (
                <MetricCard label="Score Composto" value={`${(data.baseDetail.compositeScore * 100).toFixed(0)}%`} />
              )}
            </div>
          </div>

          {/* Refiner scores */}
          {data.refiner && (
            <div style={SECTION}>
              <div style={SECTION_TITLE}>Refiner Scores</div>
              <div style={GRID}>
                <MetricCard label="Earnings Quality" value={fmtScore(data.refiner.earningsQualityScore)} />
                <MetricCard label="Safety" value={fmtScore(data.refiner.safetyScore)} />
                <MetricCard label="Consistency" value={fmtScore(data.refiner.operatingConsistencyScore)} />
                <MetricCard label="Capital Disc." value={fmtScore(data.refiner.capitalDisciplineScore)} />
              </div>
              {data.refiner.refinementScore != null && (
                <div style={{ marginTop: 8 }}>
                  <MetricCard label="Refinement Score" value={fmtScore(data.refiner.refinementScore)} />
                </div>
              )}
              {data.refiner.adjustedRank != null && (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>
                  Adjusted Rank: #{data.refiner.adjustedRank}
                </div>
              )}
            </div>
          )}

          {/* Flags */}
          {data.flags && (data.flags.red.length > 0 || data.flags.strength.length > 0) && (
            <div style={SECTION}>
              <div style={SECTION_TITLE}>Flags</div>
              <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                {data.flags.red.map((f) => <Badge key={f} text={f} variant="red" />)}
                {data.flags.strength.map((f) => <Badge key={f} text={f} variant="green" />)}
              </div>
            </div>
          )}

          {/* Trends */}
          {data.trends.length > 0 && (
            <div style={SECTION}>
              <div style={SECTION_TITLE}>Trends (3-period)</div>
              {data.trends.map((t) => (
                <div key={t.metric} style={{ marginBottom: 6 }}>
                  <div style={{ fontSize: 12, fontWeight: 500 }}>{t.metric.replace(/_/g, ' ')}</div>
                  <TrendMini values={t.values} />
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function fmtScore(v: number | null): string {
  return v != null ? `${(v * 100).toFixed(0)}%` : '—';
}
