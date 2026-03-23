'use client';

import {
  useStrategyRegistry,
  getStatusLabel,
  getStatusColor,
} from '../hooks/api/useStrategyRegistry';

/**
 * Global research context banner — NOT a source-of-data indicator.
 *
 * Shows the current empirical research state:
 * - Current live default strategy and its validation status
 * - Current research frontrunner and its status
 *
 * This is explicitly GLOBAL context — it does NOT claim that the data
 * on this specific page comes from any particular strategy config.
 * Each page's data source may differ (ranking = live default, portfolio = latest run, etc.)
 */
export function StrategyContextBanner() {
  const { data: registry } = useStrategyRegistry();

  if (!registry || registry.length === 0) return null;

  const liveDefault = registry.find((e) => e.strategyKey === 'ctrl_brazil_20m');
  const frontrunner = registry.find((e) => e.role === 'FRONTRUNNER');

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        padding: '0.4rem 1.25rem',
        borderBottom: '1px solid var(--border-color)',
        background: 'var(--bg-surface)',
        fontSize: 12,
        flexWrap: 'wrap',
      }}
    >
      <span style={{ color: 'var(--text-secondary)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        Research status
      </span>

      {liveDefault && (
        <span
          title={liveDefault.evidenceSummary}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.3rem',
            cursor: 'help',
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: getStatusColor(liveDefault.promotionStatus),
            }}
          />
          <span style={{ color: 'var(--text-secondary)' }}>
            Current default: <strong>{liveDefault.strategyKey}</strong> — {getStatusLabel(liveDefault.role, liveDefault.promotionStatus)}
          </span>
        </span>
      )}

      {frontrunner && frontrunner.strategyKey !== liveDefault?.strategyKey && (
        <span
          title={frontrunner.evidenceSummary}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.3rem',
            marginLeft: 'auto',
            cursor: 'help',
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: getStatusColor(frontrunner.promotionStatus),
            }}
          />
          <span style={{ color: 'var(--text-secondary)' }}>
            Research frontrunner: <strong>{frontrunner.strategyKey}</strong>
            {frontrunner.oosSharpeAvg != null && (
              <> (OOS Sharpe {frontrunner.oosSharpeAvg.toFixed(2)})</>
            )}
          </span>
        </span>
      )}
    </div>
  );
}
