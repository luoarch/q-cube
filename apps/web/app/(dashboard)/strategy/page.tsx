'use client';

import Link from 'next/link';
import { useState } from 'react';

import { useCreateStrategyRun, useStrategyRuns } from '../../../src/hooks/api/useStrategyRuns';

import type { StrategyRunResponse, StrategyType } from '@q3/shared-contracts';

const STRATEGY_LABELS: Record<string, string> = {
  magic_formula_original: 'Magic Formula (Original)',
  magic_formula_brazil: 'Magic Formula (Brasil)',
  magic_formula_hybrid: 'Magic Formula (Hybrid)',
};

const STATUS_COLORS: Record<string, string> = {
  pending: '#fbbf24',
  running: '#3b82f6',
  completed: '#22c55e',
  failed: '#ef4444',
};

interface RankedAsset {
  rank: number;
  ticker: string;
  name: string;
  sector: string | null;
  earningsYield: number | null;
  returnOnCapital: number | null;
  scoreDetails?: Record<string, number>;
}

function formatPct(v: number | null): string {
  if (v == null) return '—';
  return `${(v * 100).toFixed(1)}%`;
}

function RunCard({ run, expanded, onToggle }: { run: StrategyRunResponse; expanded: boolean; onToggle: () => void }) {
  const assets = (run.result?.rankedAssets ?? []) as RankedAsset[];
  const resultCount = assets.length;

  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        borderRadius: 8,
        border: expanded ? '1px solid var(--accent-gold)' : '1px solid var(--border-color)',
        transition: 'border-color 0.15s',
      }}
    >
      {/* Header row — clickable */}
      <button
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          padding: '0.75rem 1rem',
          width: '100%',
          background: 'none',
          border: 'none',
          color: 'inherit',
          cursor: 'pointer',
          textAlign: 'left',
          fontSize: 'inherit',
        }}
      >
        <span
          style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: STATUS_COLORS[run.status] ?? '#94a3b8',
            flexShrink: 0,
          }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>
            {STRATEGY_LABELS[run.strategy] ?? run.strategy}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            {new Date(run.createdAt).toLocaleString('pt-BR')}
          </div>
        </div>

        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 10,
            background: `${STATUS_COLORS[run.status] ?? '#94a3b8'}18`,
            color: STATUS_COLORS[run.status] ?? '#94a3b8',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          {run.status}
        </span>

        {run.status === 'completed' && (
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
            {resultCount} ativos
          </span>
        )}

        {run.status === 'failed' && run.errorMessage && (
          <span
            style={{ fontSize: 12, color: '#ef4444', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            title={run.errorMessage}
          >
            {run.errorMessage}
          </span>
        )}

        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--text-secondary)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ flexShrink: 0, transition: 'transform 0.15s', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Expanded: assets table */}
      {expanded && run.status === 'completed' && assets.length > 0 && (
        <div style={{ borderTop: '1px solid var(--border-color)', maxHeight: 480, overflow: 'auto' }}>
          <table className="ranking-table">
            <thead>
              <tr>
                <th style={{ width: 50, textAlign: 'center' }}>#</th>
                <th>Ticker</th>
                <th>Empresa</th>
                <th>Setor</th>
                <th style={{ textAlign: 'right' }}>EY</th>
                <th style={{ textAlign: 'right' }}>ROC</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((a) => (
                <tr key={a.ticker}>
                  <td style={{ textAlign: 'center', color: 'var(--text-secondary)', fontWeight: 600 }}>
                    {a.rank}
                  </td>
                  <td>
                    <Link
                      href={`/assets/${a.ticker}`}
                      style={{ color: 'var(--accent-gold)', textDecoration: 'none', fontWeight: 600 }}
                    >
                      {a.ticker}
                    </Link>
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: 13, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {a.name}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{a.sector}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
                    {formatPct(a.earningsYield)}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
                    {formatPct(a.returnOnCapital)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {expanded && run.status === 'completed' && assets.length === 0 && (
        <div style={{ borderTop: '1px solid var(--border-color)', padding: '1rem', color: 'var(--text-secondary)', fontSize: 13, textAlign: 'center' }}>
          Nenhum ativo ranqueado nesta execução.
        </div>
      )}
    </div>
  );
}

export default function StrategyPage() {
  const { data: runs, isLoading } = useStrategyRuns();
  const createRun = useCreateStrategyRun();
  const [selected, setSelected] = useState<StrategyType>('magic_formula_brazil');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <h1>Strategy Runs</h1>
      </header>

      <div style={{ padding: '1.5rem', maxWidth: 1100, overflow: 'auto', flex: 1 }}>
        {/* Create new run */}
        <div
          style={{
            display: 'flex',
            gap: '0.75rem',
            alignItems: 'center',
            marginBottom: '1.5rem',
            padding: '1rem',
            background: 'var(--bg-surface)',
            borderRadius: 8,
            border: '1px solid var(--border-color)',
          }}
        >
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value as StrategyType)}
            style={{
              flex: 1,
              padding: '0.5rem 0.75rem',
              background: 'var(--bg-canvas)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 6,
              fontSize: 14,
            }}
          >
            {Object.entries(STRATEGY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <button
            onClick={() => createRun.mutate({ strategy: selected })}
            disabled={createRun.isPending}
            style={{
              padding: '0.5rem 1.25rem',
              background: 'var(--accent-gold)',
              color: '#0a0e1a',
              border: 'none',
              borderRadius: 6,
              fontWeight: 600,
              fontSize: 14,
              cursor: createRun.isPending ? 'wait' : 'pointer',
              opacity: createRun.isPending ? 0.7 : 1,
            }}
          >
            {createRun.isPending ? 'Criando...' : 'Calcular Ranking'}
          </button>
        </div>

        {isLoading && (
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Carregando...</p>
        )}

        {runs && runs.length === 0 && (
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
            Nenhuma estratégia calculada. Clique em &quot;Calcular Ranking&quot; para iniciar.
          </p>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {runs?.map((run) => (
            <RunCard
              key={run.id}
              run={run}
              expanded={expandedId === run.id}
              onToggle={() => setExpandedId(expandedId === run.id ? null : run.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
