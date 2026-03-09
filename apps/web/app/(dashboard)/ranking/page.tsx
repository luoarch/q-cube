'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import { useRanking } from '../../../src/hooks/api/useRanking';

import type { RankingItem } from '@q3/shared-contracts';

const QUALITY_COLORS: Record<string, string> = {
  high: '#22c55e',
  medium: '#fbbf24',
  low: '#ef4444',
};

function formatNumber(n: number): string {
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(2);
}

function formatPercent(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

export default function RankingPage() {
  const { data: items = [], isLoading } = useRanking();
  const [sectorFilter, setSectorFilter] = useState<string | null>(null);
  const [qualityFilter, setQualityFilter] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const sectors = useMemo(
    () => [...new Set(items.map((it) => it.sector))].sort(),
    [items],
  );

  const filtered = useMemo(() => {
    let result = items;
    if (sectorFilter) result = result.filter((it) => it.sector === sectorFilter);
    if (qualityFilter) result = result.filter((it) => it.quality === qualityFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (it) => it.ticker.toLowerCase().includes(q) || it.name.toLowerCase().includes(q),
      );
    }
    return result;
  }, [items, sectorFilter, qualityFilter, search]);

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <h1>Ranking</h1>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          {filtered.length} de {items.length} ativos
        </span>
      </header>

      {/* Filters */}
      <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border-color)', display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Buscar ticker ou nome..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: '6px 12px',
            background: 'var(--bg-canvas)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: 6,
            fontSize: 13,
            width: 220,
          }}
        />
        <select
          value={sectorFilter ?? ''}
          onChange={(e) => setSectorFilter(e.target.value || null)}
          style={{
            padding: '6px 12px',
            background: 'var(--bg-canvas)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: 6,
            fontSize: 13,
          }}
        >
          <option value="">Todos os setores</option>
          {sectors.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={qualityFilter ?? ''}
          onChange={(e) => setQualityFilter(e.target.value || null)}
          style={{
            padding: '6px 12px',
            background: 'var(--bg-canvas)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: 6,
            fontSize: 13,
          }}
        >
          <option value="">Quality: Todos</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {isLoading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Carregando ranking...
          </div>
        ) : (
          <table className="ranking-table">
            <thead>
              <tr>
                <th style={{ width: 50, textAlign: 'center' }}>#</th>
                <th>Ticker</th>
                <th>Empresa</th>
                <th>Setor</th>
                <th style={{ textAlign: 'right' }}>Earnings Yield</th>
                <th style={{ textAlign: 'right' }}>ROIC</th>
                <th style={{ textAlign: 'right' }}>Market Cap</th>
                <th style={{ textAlign: 'center' }}>Quality</th>
                <th style={{ textAlign: 'center' }}>Liquidez</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.ticker}>
                  <td style={{ textAlign: 'center', color: 'var(--text-secondary)', fontWeight: 600 }}>
                    {item.magicFormulaRank}
                  </td>
                  <td>
                    <Link
                      href={`/assets/${item.ticker}`}
                      style={{ color: 'var(--accent-gold)', textDecoration: 'none', fontWeight: 600 }}
                    >
                      {item.ticker}
                    </Link>
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: 13, maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item.name}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{item.sector}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
                    {formatPercent(item.earningsYield)}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
                    {formatPercent(item.returnOnCapital)}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
                    {formatNumber(item.marketCap)}
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        padding: '2px 8px',
                        borderRadius: 10,
                        background: `${QUALITY_COLORS[item.quality] ?? '#94a3b8'}18`,
                        color: QUALITY_COLORS[item.quality] ?? '#94a3b8',
                      }}
                    >
                      {item.quality}
                    </span>
                  </td>
                  <td style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-secondary)' }}>
                    {item.liquidity}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
