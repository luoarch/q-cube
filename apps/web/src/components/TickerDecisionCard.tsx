'use client';

import type { TickerDecision } from '@q3/shared-contracts';

const STATUS_COLORS: Record<string, string> = {
  APPROVED: '#22c55e',
  BLOCKED: '#fbbf24',
  REJECTED: '#ef4444',
};

const CONFIDENCE_COLORS: Record<string, string> = {
  HIGH: '#22c55e',
  MEDIUM: '#fbbf24',
  LOW: '#ef4444',
};

const DRIVER_TYPE_COLORS: Record<string, string> = {
  structural: '#3b82f6',
  cyclical: '#a855f7',
  historical: '#94a3b8',
};

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 10, background: `${color}18`, color, letterSpacing: '0.3px' }}>
      {label}
    </span>
  );
}

export function TickerDecisionCard({ decision: d }: { decision: TickerDecision }) {
  const statusColor = STATUS_COLORS[d.decision.status] ?? '#94a3b8';
  const confColor = CONFIDENCE_COLORS[d.confidence.label] ?? '#94a3b8';

  return (
    <div style={{ background: 'var(--bg-surface)', border: `1px solid ${statusColor}30`, borderRadius: 8, padding: '1rem 1.25rem', marginTop: '1rem' }}>
      {/* Header: Status + Confidence */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Ticker Decision</h3>
        <Chip label={d.decision.status} color={statusColor} />
        <Chip label={`Confidence: ${d.confidence.label}`} color={confColor} />
        {d.decision.blockReason && (
          <span style={{ fontSize: 11, color: '#fbbf24' }}>[{d.decision.blockReason}]</span>
        )}
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 'auto' }}>
          {d.decision.reason}
        </span>
      </div>

      {/* Grid: Quality + Valuation + Yield */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '0.75rem' }}>
        {/* Quality */}
        <div style={{ background: 'var(--bg-canvas)', border: '1px solid var(--border-color)', borderRadius: 6, padding: '0.5rem 0.75rem' }}>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Quality</div>
          {d.quality ? (
            <>
              <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace' }}>{d.quality.label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Score: {d.quality.score.toFixed(2)}</div>
            </>
          ) : (
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Sem dados de refiner</div>
          )}
        </div>

        {/* Valuation */}
        <div style={{ background: 'var(--bg-canvas)', border: '1px solid var(--border-color)', borderRadius: 6, padding: '0.5rem 0.75rem' }}>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>
            Valuation <span style={{ fontSize: 9, fontWeight: 400 }}>(proxy EY)</span>
          </div>
          {d.valuation?.label ? (
            <>
              <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace' }}>{d.valuation.label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                EY: {d.valuation.earningsYield != null ? `${(d.valuation.earningsYield * 100).toFixed(1)}%` : '—'}
                {d.valuation.eySectorPercentile != null && ` (pctl ${d.valuation.eySectorPercentile.toFixed(0)})`}
              </div>
              {d.valuation.impliedValueRange ? (
                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                  Proxy range: R$ {d.valuation.impliedValueRange[0].toFixed(0)} – {d.valuation.impliedValueRange[1].toFixed(0)}
                </div>
              ) : d.valuation.suppressionReason ? (
                <div style={{ fontSize: 10, color: '#fbbf24' }} title={d.valuation.suppressionReason}>
                  Proxy valuation unavailable
                </div>
              ) : null}
            </>
          ) : (
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Sem dados</div>
          )}
        </div>

        {/* Implied Yield */}
        <div style={{ background: 'var(--bg-canvas)', border: '1px solid var(--border-color)', borderRadius: 6, padding: '0.5rem 0.75rem' }}>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>
            Implied Yield <span style={{ fontSize: 9, fontWeight: 400 }}>(sem crescimento)</span>
          </div>
          {d.impliedYield?.totalYield != null ? (
            <>
              <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace' }}>
                {(d.impliedYield.totalYield * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                EY {((d.impliedYield.earningsYield ?? 0) * 100).toFixed(1)}% + NPY {((d.impliedYield.netPayoutYield ?? 0) * 100).toFixed(1)}%
              </div>
              {d.impliedYield.outlier && (
                <div style={{ fontSize: 10, color: '#ef4444' }} title={d.impliedYield.outlierReason}>
                  Outlier — verificar EV/dados
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Sem dados</div>
          )}
        </div>
      </div>

      {/* Drivers + Risks */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.5rem' }}>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600, marginBottom: '0.3rem' }}>Drivers</div>
          {d.drivers.length > 0 ? d.drivers.map((dr, i) => (
            <div key={i} style={{ fontSize: 12, padding: '2px 0', display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
              <Chip label={dr.driverType} color={DRIVER_TYPE_COLORS[dr.driverType] ?? '#94a3b8'} />
              <span>{dr.signal}</span>
            </div>
          )) : <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Sem drivers identificados</div>}
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600, marginBottom: '0.3rem' }}>Riscos</div>
          {d.risks.length > 0 ? d.risks.map((r, i) => (
            <div key={i} style={{ fontSize: 12, padding: '2px 0', color: r.critical ? '#ef4444' : 'var(--text-primary)' }}>
              {r.critical && '⚠ '}{r.signal}
            </div>
          )) : <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Sem riscos identificados</div>}
        </div>
      </div>

      {/* Footer: Governance + Provenance */}
      <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '0.4rem', marginTop: '0.4rem' }}>
        {d.decision.governanceNote && (
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.3, marginBottom: '0.25rem' }}>
            {d.decision.governanceNote}
          </div>
        )}
        <div style={{ fontSize: 10, color: 'var(--text-secondary)', opacity: 0.7, fontFamily: 'monospace', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <span>Classificação de pesquisa, não recomendação de investimento</span>
          {d.provenance.metricsReferenceDate && <span>Ref: {d.provenance.metricsReferenceDate}</span>}
          {d.provenance.universePolicy && <span>Universo: {d.provenance.universePolicy}</span>}
        </div>
      </div>
    </div>
  );
}
