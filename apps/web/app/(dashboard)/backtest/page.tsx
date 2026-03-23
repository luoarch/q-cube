'use client';

import dynamic from 'next/dynamic';
import { useCallback, useState } from 'react';

import { useBacktestRuns, useCreateBacktestRun } from '../../../src/hooks/api/useBacktest';
import { StrategyWarningGate, StrategyExecutionBanner } from '../../../src/components/StrategyWarningGate';
import {
  useStrategyRegistry,
  getStatusLabel,
  getStatusColor,
  type StrategyRegistryEntry,
} from '../../../src/hooks/api/useStrategyRegistry';

import type { BacktestRunResponse } from '@q3/shared-contracts';

const BacktestTimelineScene = dynamic(
  () =>
    import('../../../src/components/three/scenes/BacktestTimelineScene').then(
      (m) => m.BacktestTimelineScene,
    ),
  { ssr: false },
);

const STATUS_COLORS: Record<string, string> = {
  pending: '#fbbf24',
  running: '#3b82f6',
  completed: '#22c55e',
  failed: '#ef4444',
};

/**
 * Match a run config against the registry.
 *
 * The registry stores configJson for each entry. We compare the run's config
 * against each registry entry's configJson on the canonical fields.
 * This avoids cross-language fingerprint computation (Python float vs JS number).
 */
function matchRegistry(
  runConfig: Record<string, unknown>,
  registry: StrategyRegistryEntry[] | undefined,
): StrategyRegistryEntry | null {
  if (!registry || !runConfig) return null;

  for (const entry of registry) {
    const regConfig = entry.configJson as Record<string, unknown> | undefined;
    if (!regConfig) continue;

    // Compare canonical fields
    const regCost = (regConfig.cost_model ?? {}) as Record<string, unknown>;
    const runCost = (runConfig.costModel ?? {}) as Record<string, unknown>;

    const match =
      regConfig.strategy_type === runConfig.strategyType &&
      regConfig.top_n === (runConfig.topN ?? 20) &&
      regConfig.rebalance_freq === (runConfig.rebalanceFreq ?? 'monthly') &&
      regConfig.equal_weight === (runConfig.equalWeight ?? true) &&
      Number(regCost.proportional ?? 0) === Number(runCost.proportionalCost ?? runCost.proportional ?? 0.0005) &&
      Number(regCost.slippage_bps ?? 0) === Number(runCost.slippageBps ?? runCost.slippage_bps ?? 10) &&
      (regConfig.universe_policy_version ?? 'v1') === ((runConfig as Record<string, unknown>).universePolicyVersion ?? 'v1');

    if (match) return entry;
  }
  return null;
}

function StatusChip({ entry }: { entry: StrategyRegistryEntry }) {
  const color = getStatusColor(entry.promotionStatus);
  return (
    <span
      title={entry.evidenceSummary}
      style={{
        fontSize: 9,
        fontWeight: 600,
        padding: '1px 6px',
        borderRadius: 8,
        background: `${color}18`,
        color,
        cursor: 'help',
        letterSpacing: '0.3px',
      }}
    >
      {entry.strategyKey}
    </span>
  );
}

function RunCard({
  run,
  active,
  onClick,
  registry,
}: {
  run: BacktestRunResponse;
  active: boolean;
  onClick: () => void;
  registry: StrategyRegistryEntry[] | undefined;
}) {
  const config = run.config as Record<string, unknown>;
  const entry = matchRegistry(config, registry);
  return (
    <button
      onClick={onClick}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        padding: '0.5rem 0.75rem',
        marginBottom: 4,
        background: active ? 'rgba(251,191,36,0.1)' : 'transparent',
        border: active ? '1px solid rgba(251,191,36,0.3)' : '1px solid transparent',
        borderRadius: 6,
        color: 'var(--text-primary, #e2e8f0)',
        cursor: 'pointer',
        fontSize: 13,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 500 }}>
          {(config?.strategyType as string) ?? 'backtest'}
        </span>
        <span
          style={{
            fontSize: 10,
            padding: '1px 6px',
            borderRadius: 8,
            background: `${STATUS_COLORS[run.status] ?? '#94a3b8'}22`,
            color: STATUS_COLORS[run.status] ?? '#94a3b8',
            fontWeight: 600,
          }}
        >
          {run.status}
        </span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        {new Date(run.createdAt).toLocaleDateString('pt-BR')} · Top {(config?.topN as number) ?? 20}
        {entry && <StatusChip entry={entry} />}
      </div>
    </button>
  );
}

function MetricDisplay({ label, value, suffix }: { label: string; value: number | undefined; suffix?: string }) {
  if (value == null) return null;
  return (
    <div
      style={{
        background: 'rgba(148,163,184,0.06)',
        padding: '0.5rem 0.75rem',
        borderRadius: 8,
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 600 }}>
        {(value * 100).toFixed(2)}{suffix ?? '%'}
      </div>
    </div>
  );
}

export default function BacktestPage() {
  const { data: runs } = useBacktestRuns();
  const createRun = useCreateBacktestRun();
  const { data: registry } = useStrategyRegistry();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const selectedRun = runs?.find((r) => r.id === selectedRunId);
  const metrics = selectedRun?.result?.metrics as Record<string, number> | undefined;
  const selectedConfig = selectedRun?.config as Record<string, unknown> | undefined;
  const selectedEntry = selectedConfig ? matchRegistry(selectedConfig, registry) : null;

  const handleCreate = useCallback(() => {
    createRun.mutate(
      {
        config: {
          strategyType: 'magic_formula_brazil',
          startDate: '2020-01-01',
          endDate: '2024-12-31',
          rebalanceFreq: 'monthly',
          executionLagDays: 1,
          topN: 20,
          equalWeight: true,
          initialCapital: 1_000_000,
        },
      },
      {
        onSuccess: (run) => setSelectedRunId(run.id),
      },
    );
  }, [createRun]);

  return (
    <div className="dashboard-page" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <header className="dashboard-header">
        <h1>Backtest Timeline</h1>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar */}
        <div
          style={{
            width: 240,
            borderRight: '1px solid rgba(148,163,184,0.15)',
            padding: '1rem',
            overflowY: 'auto',
          }}
        >
          <div style={{ marginBottom: 12 }}>
            <StrategyWarningGate
              strategyType="magic_formula_brazil"
              onConfirm={handleCreate}
              isPending={createRun.isPending}
              buttonLabel="+ Novo Backtest"
            />
          </div>

          {runs?.map((run) => (
            <RunCard
              key={run.id}
              run={run}
              active={run.id === selectedRunId}
              onClick={() => setSelectedRunId(run.id)}
              registry={registry}
            />
          ))}

          {!runs?.length && (
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', textAlign: 'center', marginTop: 20 }}>
              Nenhum backtest encontrado.
            </div>
          )}
        </div>

        {/* Main area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {selectedRunId && selectedRun ? (
            <>
              {/* Persistent execution status banner */}
              {selectedConfig?.strategyType && (
                <StrategyExecutionBanner strategyType={selectedConfig.strategyType as string} />
              )}

              {/* Strategy status banner (config-level) */}
              {selectedEntry && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    padding: '0.5rem 1rem',
                    borderBottom: '1px solid rgba(148,163,184,0.15)',
                    background: `${getStatusColor(selectedEntry.promotionStatus)}08`,
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: getStatusColor(selectedEntry.promotionStatus),
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ fontSize: 12, fontWeight: 600 }}>{selectedEntry.strategyKey}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    {getStatusLabel(selectedEntry.role, selectedEntry.promotionStatus)}
                  </span>
                  {selectedEntry.oosSharpeAvg != null && (
                    <span style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                      OOS Sharpe {selectedEntry.oosSharpeAvg.toFixed(2)}
                    </span>
                  )}
                </div>
              )}

              {/* Metrics bar */}
              {metrics && (
                <div
                  style={{
                    display: 'flex',
                    gap: 8,
                    padding: '0.75rem 1rem',
                    borderBottom: '1px solid rgba(148,163,184,0.15)',
                    overflowX: 'auto',
                  }}
                >
                  <MetricDisplay label="CAGR" value={metrics.cagr} />
                  <MetricDisplay label="Sharpe" value={metrics.sharpe} suffix="" />
                  <MetricDisplay label="Max DD" value={metrics.maxDrawdown} />
                  <MetricDisplay label="Volatilidade" value={metrics.volatility} />
                  <MetricDisplay label="Sortino" value={metrics.sortino} suffix="" />
                  <MetricDisplay label="Hit Rate" value={metrics.hitRate} />
                </div>
              )}

              {/* 3D Scene */}
              <div className="dashboard-scene" style={{ flex: 1 }}>
                <BacktestTimelineScene runId={selectedRunId} />
              </div>
            </>
          ) : (
            <div
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--text-secondary)',
                fontSize: 14,
              }}
            >
              Selecione ou crie um backtest para visualizar.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
