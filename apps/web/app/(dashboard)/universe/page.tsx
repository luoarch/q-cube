'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import { useUniverse } from '../../../src/hooks/api/useUniverse';

function formatNumber(n: number): string {
  if (n === 0) return '—';
  if (Math.abs(n) >= 1e12) return `R$ ${(n / 1e12).toFixed(1)}T`;
  if (Math.abs(n) >= 1e9) return `R$ ${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `R$ ${(n / 1e6).toFixed(0)}M`;
  return `R$ ${n.toFixed(0)}`;
}

function StatCard({ label, value, subtitle }: { label: string; value: string; subtitle?: string | undefined }) {
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
        {value}
      </div>
      {subtitle && (
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{subtitle}</div>
      )}
    </div>
  );
}

function SectorBar({ name, count, marketCap, maxCount }: { name: string; count: number; marketCap: number; maxCount: number }) {
  const pct = maxCount > 0 ? count / maxCount : 0;
  return (
    <tr>
      <td style={{ padding: '8px 12px', fontWeight: 500 }}>{name}</td>
      <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>{count}</td>
      <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>{formatNumber(marketCap)}</td>
      <td style={{ padding: '8px 12px', width: '30%' }}>
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

export default function UniversePage() {
  const { data: universe, isLoading } = useUniverse();
  const [search, setSearch] = useState('');

  const totalMarketCap = useMemo(
    () => universe?.sectors.reduce((sum, s) => sum + s.marketCap, 0) ?? 0,
    [universe],
  );

  const sectorCount = useMemo(
    () => universe?.sectors.filter((s) => s.name !== 'Sem Setor').length ?? 0,
    [universe],
  );

  const filteredSectors = useMemo(() => {
    if (!universe) return [];
    let sectors = universe.sectors;
    if (search) {
      const q = search.toLowerCase();
      sectors = sectors.filter((s) => s.name.toLowerCase().includes(q));
    }
    return sectors;
  }, [universe, search]);

  const maxCount = useMemo(
    () => Math.max(...(filteredSectors.map((s) => s.count) || [1]), 1),
    [filteredSectors],
  );

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <h1>Universo</h1>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Visao geral do universo de ativos
        </span>
      </header>

      {isLoading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Carregando universo...
        </div>
      ) : !universe ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Sem dados disponiveis.
        </div>
      ) : (
        <div style={{ padding: '1.25rem', overflow: 'auto', flex: 1 }}>
          {/* Summary stats */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: '0.75rem',
              marginBottom: '1.5rem',
            }}
          >
            <StatCard label="Total de Ativos" value={String(universe.totalStocks)} />
            <StatCard label="Setores" value={String(sectorCount)} subtitle={sectorCount === 0 ? 'Cadastro pendente' : undefined} />
            <StatCard label="Market Cap Total" value={formatNumber(totalMarketCap)} subtitle="Ativos com dados de mercado" />
            <StatCard
              label="Com Market Cap"
              value={String(universe.sectors.reduce((sum, s) => sum + (s.marketCap > 0 ? s.count : 0), 0))}
              subtitle={`de ${universe.totalStocks} ativos`}
            />
          </div>

          {/* Quick links */}
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
            <Link
              href="/ranking"
              style={{
                padding: '8px 16px',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                color: 'var(--accent-gold)',
                textDecoration: 'none',
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              Ver Ranking
            </Link>
            <Link
              href="/compare"
              style={{
                padding: '8px 16px',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                color: 'var(--text-secondary)',
                textDecoration: 'none',
                fontSize: 13,
              }}
            >
              Comparar Ativos
            </Link>
          </div>

          {/* Sector breakdown */}
          <div
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: 8,
              overflow: 'hidden',
            }}
          >
            <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
                Distribuicao por Setor
              </h3>
              <input
                type="text"
                placeholder="Filtrar setor..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{
                  marginLeft: 'auto',
                  padding: '4px 10px',
                  background: 'var(--bg-canvas)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 6,
                  fontSize: 12,
                  width: 180,
                }}
              />
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Setor</th>
                  <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Ativos</th>
                  <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Market Cap</th>
                  <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Distribuicao</th>
                </tr>
              </thead>
              <tbody>
                {filteredSectors.map((s) => (
                  <SectorBar
                    key={s.name}
                    name={s.name}
                    count={s.count}
                    marketCap={s.marketCap}
                    maxCount={maxCount}
                  />
                ))}
                {filteredSectors.length === 0 && (
                  <tr>
                    <td colSpan={4} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                      Nenhum setor encontrado.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
