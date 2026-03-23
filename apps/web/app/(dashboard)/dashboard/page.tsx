'use client';

import Link from 'next/link';
import { useMemo } from 'react';

import { useDashboard } from '../../../src/hooks/api/useDashboard';
import { StrategyContextBanner } from '../../../src/components/StrategyContextBanner';

const STAGE_COLORS: Record<string, string> = {
  completed: '#22c55e',
  running: '#3b82f6',
  pending: '#fbbf24',
  failed: '#ef4444',
  idle: '#94a3b8',
};

function formatKpiValue(value: number | string, format?: string): string {
  if (format === 'percent') return `${value}%`;
  return String(value);
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${day}/${month}/${year} ${hours}:${minutes}`;
}

function KpiCard({ label, value, format }: { label: string; value: number | string; format?: string | undefined }) {
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
        {formatKpiValue(value, format)}
      </div>
    </div>
  );
}

function PipelineStatus({ stage, progress, lastRun }: { stage: string; progress: number; lastRun: string | null }) {
  const color = STAGE_COLORS[stage] ?? '#94a3b8';
  const clampedProgress = Math.min(Math.max(progress, 0), 100);
  const stageLabel = stage.charAt(0).toUpperCase() + stage.slice(1);

  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-color)',
        borderRadius: 8,
        padding: '1rem 1.25rem',
      }}
    >
      <h3 style={{ margin: '0 0 0.75rem', fontSize: 14, fontWeight: 600 }}>Pipeline</h3>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 10,
            background: `${color}18`,
            color,
            letterSpacing: '0.5px',
          }}
        >
          {stageLabel}
        </span>
        <div style={{ flex: 1, height: 8, background: 'var(--grid-color)', borderRadius: 4, overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              width: `${clampedProgress}%`,
              background: color,
              borderRadius: 4,
              transition: 'width 0.3s ease',
            }}
          />
        </div>
        <span style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--text-secondary)', flexShrink: 0 }}>
          {clampedProgress}%
        </span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
        {lastRun ? formatDate(lastRun) : 'Nenhuma execucao'}
      </div>
    </div>
  );
}

function SectorBar({ name, count, maxCount }: { name: string; count: number; maxCount: number }) {
  const pct = maxCount > 0 ? count / maxCount : 0;
  return (
    <tr>
      <td style={{ padding: '8px 12px', fontWeight: 500 }}>{name}</td>
      <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>{count}</td>
      <td style={{ padding: '8px 12px', width: '40%' }}>
        <div style={{ height: 8, background: 'var(--grid-color)', borderRadius: 4, overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              width: `${pct * 100}%`,
              background: 'var(--accent-gold)',
              borderRadius: 4,
              transition: 'width 0.3s ease',
            }}
          />
        </div>
      </td>
    </tr>
  );
}

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard();

  const sortedSectors = useMemo(() => {
    if (!data?.sectorDistribution) return [];
    return [...data.sectorDistribution].sort((a, b) => b.value - a.value);
  }, [data]);

  const maxSectorCount = useMemo(
    () => Math.max(...(sortedSectors.map((s) => s.value) || [1]), 1),
    [sortedSectors],
  );

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <h1>Dashboard</h1>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Visao geral do sistema
        </span>
      </header>

      <StrategyContextBanner />

      {isLoading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Carregando dashboard...
        </div>
      ) : error ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#ef4444' }}>
          Erro ao carregar dashboard.
        </div>
      ) : !data ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Sem dados disponiveis.
        </div>
      ) : (
        <div style={{ padding: '1.25rem', overflow: 'auto', flex: 1 }}>
          {/* KPI Cards */}
          {data.kpis.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: '0.75rem',
                marginBottom: '1.5rem',
              }}
            >
              {data.kpis.map((kpi) => (
                <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} format={kpi.format} />
              ))}
            </div>
          )}

          {/* Pipeline Status */}
          <div style={{ marginBottom: '1.5rem' }}>
            <PipelineStatus
              stage={data.pipelineStatus.stage}
              progress={data.pipelineStatus.progress}
              lastRun={data.pipelineStatus.lastRun}
            />
          </div>

          {/* Top Ranked */}
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
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Top Ranked</h3>
            </div>
            {data.topRanked.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Nenhum ativo ranqueado.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <th style={{ padding: '8px 12px', textAlign: 'center', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600, width: 50 }}>#</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Ticker</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Empresa</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Preco</th>
                  </tr>
                </thead>
                <tbody>
                  {data.topRanked.map((item) => (
                    <tr key={item.ticker}>
                      <td style={{ padding: '8px 12px', textAlign: 'center', color: 'var(--text-secondary)', fontWeight: 600 }}>
                        {item.rank}
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <Link
                          href={`/assets/${item.ticker}`}
                          style={{ color: 'var(--accent-gold)', textDecoration: 'none', fontWeight: 600 }}
                        >
                          {item.ticker}
                        </Link>
                      </td>
                      <td style={{ padding: '8px 12px', color: 'var(--text-secondary)', fontSize: 13, maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.name}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
                        {item.price != null ? `R$ ${item.price.toFixed(2)}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Sector Distribution */}
          <div
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: 8,
              overflow: 'hidden',
            }}
          >
            <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)' }}>
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Distribuicao por Setor</h3>
            </div>
            {sortedSectors.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                Sem dados de setor.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Setor</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Ativos</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Distribuicao</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedSectors.map((s) => (
                    <SectorBar key={s.name} name={s.name} count={s.value} maxCount={maxSectorCount} />
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
