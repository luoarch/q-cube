'use client';

import {
  useMonitoringSummary,
  useDrift,
  useRubricAging,
  useReviewQueue,
  useMonitoringAlerts,
} from '../../../../src/hooks/api/useThesisMonitoring';

import type {
  AlertItem,
  DimensionCoverage,
  DriftDetail,
  ReviewItem,
  StaleRubric,
} from '../../../../src/hooks/api/useThesisMonitoring';

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const card = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  padding: '1rem 1.25rem',
} as const;

const cardHeader = {
  fontSize: 14,
  fontWeight: 700,
  marginBottom: 12,
} as const;

const labelStyle = {
  fontSize: 11,
  color: 'var(--text-secondary)',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.5px',
  fontWeight: 600,
} as const;

const monoSmall = {
  fontFamily: 'monospace',
  fontSize: 12,
} as const;

const PRIORITY_COLORS: Record<string, string> = {
  HIGH: '#ef4444',
  MEDIUM: '#f59e0b',
  LOW: '#94a3b8',
};

const SOURCE_COLORS: Record<string, string> = {
  QUANTITATIVE: '#22c55e',
  RUBRIC_MANUAL: '#3b82f6',
  AI_ASSISTED: '#8b5cf6',
  SECTOR_PROXY: '#f59e0b',
  DERIVED: '#06b6d4',
  DEFAULT: '#94a3b8',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 10,
        background: `${color}18`,
        color,
        letterSpacing: '0.3px',
      }}
    >
      {label}
    </span>
  );
}

function BarSegment({ pct, color, label }: { pct: number; color: string; label: string }) {
  if (pct <= 0) return null;
  return (
    <div
      title={`${label}: ${pct.toFixed(1)}%`}
      style={{
        height: 20,
        width: `${pct}%`,
        background: color,
        minWidth: pct > 0 ? 2 : 0,
      }}
    />
  );
}

function ProvenanceBar({ mix, mixPct }: { mix: Record<string, number>; mixPct: Record<string, number> }) {
  const order = ['QUANTITATIVE', 'RUBRIC_MANUAL', 'AI_ASSISTED', 'SECTOR_PROXY', 'DERIVED', 'DEFAULT'];
  return (
    <div>
      <div style={{ display: 'flex', borderRadius: 4, overflow: 'hidden', marginBottom: 8 }}>
        {order.map((key) => (
          <BarSegment key={key} pct={mixPct[key] ?? 0} color={SOURCE_COLORS[key] ?? '#666'} label={key} />
        ))}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {order.map((key) => {
          const count = mix[key];
          if (!count) return null;
          return (
            <span key={key} style={{ ...monoSmall, display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: SOURCE_COLORS[key] ?? '#666' }} />
              {key}: {count} ({(mixPct[key] ?? 0).toFixed(1)}%)
            </span>
          );
        })}
      </div>
    </div>
  );
}

function DimensionTable({ dimensions }: { dimensions: DimensionCoverage[] }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 8 }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
          <th style={{ ...labelStyle, padding: '6px 8px', textAlign: 'left' }}>Dimension</th>
          <th style={{ ...labelStyle, padding: '6px 8px', textAlign: 'right' }}>Issuers</th>
          <th style={{ ...labelStyle, padding: '6px 8px', textAlign: 'right' }}>Non-Default %</th>
          <th style={{ ...labelStyle, padding: '6px 8px', textAlign: 'left' }}>Sources</th>
        </tr>
      </thead>
      <tbody>
        {dimensions.map((d) => (
          <tr key={d.dimension_key} style={{ borderBottom: '1px solid var(--grid-color, #1a1f2e)' }}>
            <td style={{ padding: '6px 8px', ...monoSmall }}>{d.dimension_key}</td>
            <td style={{ padding: '6px 8px', textAlign: 'right', ...monoSmall }}>{d.total_issuers}</td>
            <td style={{ padding: '6px 8px', textAlign: 'right', ...monoSmall }}>
              <span style={{ color: d.non_default_pct >= 80 ? '#22c55e' : d.non_default_pct >= 50 ? '#f59e0b' : '#ef4444' }}>
                {d.non_default_pct.toFixed(1)}%
              </span>
            </td>
            <td style={{ padding: '6px 8px' }}>
              <div style={{ display: 'flex', gap: 4 }}>
                {Object.entries(d.source_type_counts).map(([src, count]) => (
                  <Badge key={src} label={`${src}: ${count}`} color={SOURCE_COLORS[src] ?? '#666'} />
                ))}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// Cards
// ---------------------------------------------------------------------------

function MonitoringCard() {
  const { data, isLoading, error } = useMonitoringSummary();

  if (isLoading) return <div style={card}>Carregando monitoring...</div>;
  if (error) return <div style={{ ...card, borderColor: '#ef4444' }}>Erro: {(error as Error).message}</div>;
  if (!data) return <div style={card}>Sem dados de monitoring.</div>;

  const evDist = data.evidence_quality_distribution;
  const evPct = data.evidence_quality_pct;

  return (
    <div style={card}>
      <div style={cardHeader}>Monitoring Summary</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
        Run {data.run_id.slice(0, 8)}... | {data.total_eligible} eligible issuers
      </div>

      {/* Evidence Quality Distribution */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ ...labelStyle, marginBottom: 6 }}>Evidence Quality</div>
        <div style={{ display: 'flex', borderRadius: 4, overflow: 'hidden', marginBottom: 6 }}>
          <BarSegment pct={evPct.HIGH_EVIDENCE ?? 0} color="#22c55e" label="HIGH" />
          <BarSegment pct={evPct.MIXED_EVIDENCE ?? 0} color="#f59e0b" label="MIXED" />
          <BarSegment pct={evPct.LOW_EVIDENCE ?? 0} color="#ef4444" label="LOW" />
        </div>
        <div style={{ display: 'flex', gap: 16, ...monoSmall }}>
          <span style={{ color: '#22c55e' }}>HIGH: {evDist.HIGH_EVIDENCE ?? 0} ({(evPct.HIGH_EVIDENCE ?? 0).toFixed(1)}%)</span>
          <span style={{ color: '#f59e0b' }}>MIXED: {evDist.MIXED_EVIDENCE ?? 0} ({(evPct.MIXED_EVIDENCE ?? 0).toFixed(1)}%)</span>
          <span style={{ color: '#ef4444' }}>LOW: {evDist.LOW_EVIDENCE ?? 0} ({(evPct.LOW_EVIDENCE ?? 0).toFixed(1)}%)</span>
        </div>
      </div>

      {/* Provenance Mix */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ ...labelStyle, marginBottom: 6 }}>Provenance Mix</div>
        <ProvenanceBar mix={data.provenance_mix} mixPct={data.provenance_mix_pct} />
      </div>

      {/* Dimension Coverage */}
      <div>
        <div style={{ ...labelStyle, marginBottom: 4 }}>Coverage by Dimension</div>
        <DimensionTable dimensions={data.dimension_coverage} />
      </div>
    </div>
  );
}

function DriftCard() {
  const { data, isLoading, error } = useDrift();

  if (isLoading) return <div style={card}>Carregando drift...</div>;
  if (error) {
    const msg = (error as Error).message;
    if (msg.includes('404')) return <div style={card}><div style={cardHeader}>Drift</div><div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Nenhuma run anterior para comparacao.</div></div>;
    return <div style={{ ...card, borderColor: '#ef4444' }}>Erro: {msg}</div>;
  }
  if (!data) return <div style={card}>Sem dados de drift.</div>;
  if (data.error) return <div style={card}><div style={cardHeader}>Drift</div><div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{data.error}</div></div>;

  const hasChanges = data.bucket_changes > 0 || data.top10_entered.length > 0 || data.new_issuers.length > 0;

  return (
    <div style={card}>
      <div style={cardHeader}>Drift vs Previous Run</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
        {data.current_run_id.slice(0, 8)}... vs {data.previous_run_id.slice(0, 8)}...
      </div>

      {!hasChanges ? (
        <div style={{ fontSize: 13, color: '#22c55e', padding: '8px 0' }}>
          Zero changes detected. Ranking is stable.
        </div>
      ) : (
        <>
          {/* Summary */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
            <div style={{ padding: 8, background: 'var(--bg-canvas)', borderRadius: 6, textAlign: 'center' }}>
              <div style={{ ...labelStyle, fontSize: 10 }}>Bucket Changes</div>
              <div style={{ ...monoSmall, fontSize: 18, fontWeight: 700, color: data.bucket_changes > 0 ? '#f59e0b' : '#22c55e' }}>
                {data.bucket_changes}
              </div>
            </div>
            <div style={{ padding: 8, background: 'var(--bg-canvas)', borderRadius: 6, textAlign: 'center' }}>
              <div style={{ ...labelStyle, fontSize: 10 }}>Top-10 Changes</div>
              <div style={{ ...monoSmall, fontSize: 18, fontWeight: 700 }}>
                {data.top10_entered.length + data.top10_exited.length}
              </div>
            </div>
            <div style={{ padding: 8, background: 'var(--bg-canvas)', borderRadius: 6, textAlign: 'center' }}>
              <div style={{ ...labelStyle, fontSize: 10 }}>Avg Frag Delta</div>
              <div style={{ ...monoSmall, fontSize: 18, fontWeight: 700 }}>
                {data.fragility_delta_avg != null ? data.fragility_delta_avg.toFixed(1) : '—'}
              </div>
            </div>
          </div>

          {/* Bucket change details */}
          {data.bucket_change_details.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ ...labelStyle, marginBottom: 4 }}>Bucket Changes</div>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'left' }}>Ticker</th>
                    <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'left' }}>Old</th>
                    <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'left' }}>New</th>
                    <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'right' }}>Frag Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {data.bucket_change_details.map((d: DriftDetail) => (
                    <tr key={d.issuer_id} style={{ borderBottom: '1px solid var(--grid-color, #1a1f2e)' }}>
                      <td style={{ padding: '4px 8px', ...monoSmall, fontWeight: 600 }}>{d.ticker}</td>
                      <td style={{ padding: '4px 8px', ...monoSmall }}>{d.old_bucket ?? '—'}</td>
                      <td style={{ padding: '4px 8px', ...monoSmall }}>{d.new_bucket ?? '—'}</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right', ...monoSmall }}>
                        {d.fragility_delta != null ? (d.fragility_delta > 0 ? '+' : '') + d.fragility_delta.toFixed(1) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Top-10 changes */}
          {(data.top10_entered.length > 0 || data.top10_exited.length > 0) && (
            <div style={{ display: 'flex', gap: 16 }}>
              {data.top10_entered.length > 0 && (
                <div>
                  <div style={{ ...labelStyle, marginBottom: 4, color: '#22c55e' }}>Entered Top 10</div>
                  {data.top10_entered.map((t: string) => (
                    <div key={t} style={{ ...monoSmall, color: '#22c55e' }}>+ {t}</div>
                  ))}
                </div>
              )}
              {data.top10_exited.length > 0 && (
                <div>
                  <div style={{ ...labelStyle, marginBottom: 4, color: '#ef4444' }}>Exited Top 10</div>
                  {data.top10_exited.map((t: string) => (
                    <div key={t} style={{ ...monoSmall, color: '#ef4444' }}>- {t}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function AgingCard() {
  const { data, isLoading, error } = useRubricAging();

  if (isLoading) return <div style={card}>Carregando aging...</div>;
  if (error) return <div style={{ ...card, borderColor: '#ef4444' }}>Erro: {(error as Error).message}</div>;
  if (!data) return <div style={card}>Sem dados de aging.</div>;

  return (
    <div style={card}>
      <div style={cardHeader}>Rubric Aging</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
        Threshold: {data.stale_threshold_days} days | {data.total_active_rubrics} active rubrics
      </div>

      {/* Summary */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 12, ...monoSmall }}>
        <span>
          Stale: <span style={{ color: data.stale_count > 0 ? '#f59e0b' : '#22c55e', fontWeight: 700 }}>
            {data.stale_count}
          </span> ({data.stale_pct.toFixed(1)}%)
        </span>
        <span>Fresh: {data.total_active_rubrics - data.stale_count}</span>
      </div>

      {/* Stale by dimension */}
      {Object.keys(data.stale_by_dimension).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ ...labelStyle, marginBottom: 4 }}>Stale by Dimension</div>
          <div style={{ display: 'flex', gap: 8 }}>
            {Object.entries(data.stale_by_dimension).map(([dim, count]) => (
              <Badge key={dim} label={`${dim}: ${count}`} color="#f59e0b" />
            ))}
          </div>
        </div>
      )}

      {/* Stale list (top 10) */}
      {data.stale_rubrics.length > 0 && (
        <div>
          <div style={{ ...labelStyle, marginBottom: 4 }}>Oldest Stale Rubrics</div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'left' }}>Ticker</th>
                <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'left' }}>Dimension</th>
                <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'right' }}>Age</th>
                <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'left' }}>Source</th>
              </tr>
            </thead>
            <tbody>
              {data.stale_rubrics.slice(0, 10).map((s: StaleRubric, i: number) => (
                <tr key={`${s.issuer_id}-${s.dimension_key}-${i}`} style={{ borderBottom: '1px solid var(--grid-color, #1a1f2e)' }}>
                  <td style={{ padding: '4px 8px', ...monoSmall, fontWeight: 600 }}>{s.ticker}</td>
                  <td style={{ padding: '4px 8px', ...monoSmall }}>{s.dimension_key}</td>
                  <td style={{ padding: '4px 8px', textAlign: 'right', ...monoSmall }}>
                    {s.age_days != null ? `${s.age_days}d` : '—'}
                  </td>
                  <td style={{ padding: '4px 8px' }}>
                    <Badge label={s.source_type} color={SOURCE_COLORS[s.source_type] ?? '#666'} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.stale_rubrics.length > 10 && (
            <div style={{ ...monoSmall, color: 'var(--text-secondary)', padding: '8px', textAlign: 'center' }}>
              +{data.stale_rubrics.length - 10} more
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewQueueCard() {
  const { data, isLoading, error } = useReviewQueue();

  if (isLoading) return <div style={card}>Carregando review queue...</div>;
  if (error) return <div style={{ ...card, borderColor: '#ef4444' }}>Erro: {(error as Error).message}</div>;
  if (!data) return <div style={card}>Sem dados de review queue.</div>;

  return (
    <div style={card}>
      <div style={cardHeader}>Review Queue</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
        {data.total_items} items pending review
      </div>

      {/* Priority summary */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        {data.high_priority > 0 && (
          <div style={{ padding: '6px 12px', background: '#ef444418', borderRadius: 6, textAlign: 'center' }}>
            <div style={{ ...labelStyle, fontSize: 10, color: '#ef4444' }}>HIGH</div>
            <div style={{ ...monoSmall, fontSize: 20, fontWeight: 700, color: '#ef4444' }}>{data.high_priority}</div>
          </div>
        )}
        {data.medium_priority > 0 && (
          <div style={{ padding: '6px 12px', background: '#f59e0b18', borderRadius: 6, textAlign: 'center' }}>
            <div style={{ ...labelStyle, fontSize: 10, color: '#f59e0b' }}>MEDIUM</div>
            <div style={{ ...monoSmall, fontSize: 20, fontWeight: 700, color: '#f59e0b' }}>{data.medium_priority}</div>
          </div>
        )}
        {data.low_priority > 0 && (
          <div style={{ padding: '6px 12px', background: '#94a3b818', borderRadius: 6, textAlign: 'center' }}>
            <div style={{ ...labelStyle, fontSize: 10, color: '#94a3b8' }}>LOW</div>
            <div style={{ ...monoSmall, fontSize: 20, fontWeight: 700, color: '#94a3b8' }}>{data.low_priority}</div>
          </div>
        )}
        {data.total_items === 0 && (
          <div style={{ fontSize: 13, color: '#22c55e', padding: '8px 0' }}>
            No items need review.
          </div>
        )}
      </div>

      {/* Item list */}
      {data.items.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
              <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'left' }}>Priority</th>
              <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'left' }}>Ticker</th>
              <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'left' }}>Dimension</th>
              <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'left' }}>Reasons</th>
              <th style={{ ...labelStyle, padding: '4px 8px', textAlign: 'right' }}>Score</th>
            </tr>
          </thead>
          <tbody>
            {data.items.slice(0, 20).map((item: ReviewItem, i: number) => (
              <tr key={`${item.issuer_id}-${item.dimension_key}-${i}`} style={{ borderBottom: '1px solid var(--grid-color, #1a1f2e)' }}>
                <td style={{ padding: '4px 8px' }}>
                  <Badge label={item.priority} color={PRIORITY_COLORS[item.priority] ?? '#666'} />
                </td>
                <td style={{ padding: '4px 8px', ...monoSmall, fontWeight: 600 }}>{item.ticker}</td>
                <td style={{ padding: '4px 8px', ...monoSmall }}>{item.dimension_key}</td>
                <td style={{ padding: '4px 8px', fontSize: 11, color: 'var(--text-secondary)' }}>
                  {item.reasons.join(' | ')}
                </td>
                <td style={{ padding: '4px 8px', textAlign: 'right', ...monoSmall }}>{item.current_score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {data.items.length > 20 && (
        <div style={{ ...monoSmall, color: 'var(--text-secondary)', padding: '8px', textAlign: 'center' }}>
          +{data.items.length - 20} more items
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alerts Banner (F3.3)
// ---------------------------------------------------------------------------

const SEVERITY_STYLES = {
  CRITICAL: { bg: '#ef444418', border: '#ef4444', color: '#ef4444', icon: '!!' },
  WARNING: { bg: '#f59e0b18', border: '#f59e0b', color: '#f59e0b', icon: '!' },
  INFO: { bg: '#3b82f618', border: '#3b82f6', color: '#3b82f6', icon: 'i' },
} as const;

const DEFAULT_SEVERITY_STYLE = SEVERITY_STYLES.INFO;

function AlertsBanner() {
  const { data, isLoading } = useMonitoringAlerts();

  if (isLoading || !data || data.alert_count === 0) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
      {data.alerts.map((alert: AlertItem, i: number) => {
        const sev = alert.severity as keyof typeof SEVERITY_STYLES;
        const style = SEVERITY_STYLES[sev] ?? DEFAULT_SEVERITY_STYLE;
        return (
          <div
            key={`${alert.code}-${i}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 16px',
              background: style.bg,
              border: `1px solid ${style.border}`,
              borderRadius: 8,
            }}
          >
            <span
              style={{
                width: 24,
                height: 24,
                borderRadius: '50%',
                background: style.border,
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 11,
                fontWeight: 800,
                flexShrink: 0,
              }}
            >
              {style.icon}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: style.color }}>
                {alert.title}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                {alert.message}
              </div>
            </div>
            <Badge label={alert.severity} color={style.color} />
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ThesisMonitoringPage() {
  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Thesis Monitoring</h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            F3 — Governance dashboard for Plan 2 ranking quality
          </p>
        </div>
      </header>

      <div style={{ padding: '1.25rem', overflow: 'auto', flex: 1 }}>
        <AlertsBanner />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
          <MonitoringCard />
          <DriftCard />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <AgingCard />
          <ReviewQueueCard />
        </div>
      </div>
    </div>
  );
}
