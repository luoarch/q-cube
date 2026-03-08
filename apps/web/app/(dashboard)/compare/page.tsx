'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';

import { useComparison } from '../../../src/hooks/api/useComparison';

import type { ComparisonMatrix, MetricComparison, WinnerSummary } from '@q3/shared-contracts';

function outcomeColor(outcome: string, isWinner: boolean): string {
  if (outcome === 'inconclusive') return 'var(--text-secondary, #64748b)';
  if (outcome === 'tie') return 'var(--accent-gold, #fbbf24)';
  return isWinner ? '#34d399' : '#f87171';
}

function SummaryCard({ summary }: { summary: WinnerSummary }) {
  return (
    <div style={{
      background: 'rgba(148,163,184,0.06)',
      borderRadius: 8,
      padding: '1rem',
      textAlign: 'center',
      minWidth: 140,
    }}>
      <div style={{ fontSize: 18, fontWeight: 700 }}>{summary.ticker}</div>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 8 }}>
        <span style={{ color: '#34d399', fontSize: 13 }}>{summary.wins}W</span>
        <span style={{ color: 'var(--accent-gold, #fbbf24)', fontSize: 13 }}>{summary.ties}T</span>
        <span style={{ color: '#f87171', fontSize: 13 }}>{summary.losses}L</span>
      </div>
    </div>
  );
}

function MetricRow({ row, tickers }: { row: MetricComparison; tickers: string[] }) {
  return (
    <tr>
      <td style={{ padding: '0.5rem 0.75rem', fontSize: 13, fontWeight: 500 }}>
        {row.metric.replace(/_/g, ' ')}
      </td>
      {tickers.map((t) => {
        const val = row.values[t];
        const isWinner = row.winner === t;
        return (
          <td
            key={t}
            style={{
              padding: '0.5rem 0.75rem',
              textAlign: 'right',
              fontSize: 13,
              color: outcomeColor(row.outcome, isWinner),
              fontWeight: isWinner ? 700 : 400,
            }}
          >
            {val != null ? val.toFixed(4) : '—'}
            {isWinner && ' *'}
          </td>
        );
      })}
      <td style={{ padding: '0.5rem 0.75rem', textAlign: 'center', fontSize: 11, color: 'var(--text-secondary)' }}>
        {row.outcome}
      </td>
    </tr>
  );
}

function ComparisonResult({ data }: { data: ComparisonMatrix }) {
  return (
    <div>
      <div style={{ display: 'flex', gap: 16, marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        {data.summaries.map((s) => (
          <SummaryCard key={s.ticker} summary={s} />
        ))}
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(148,163,184,0.15)' }}>
            <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)' }}>
              Metric
            </th>
            {data.tickers.map((t) => (
              <th key={t} style={{ padding: '0.5rem 0.75rem', textAlign: 'right', fontSize: 12, color: 'var(--text-secondary)' }}>
                {t}
              </th>
            ))}
            <th style={{ padding: '0.5rem 0.75rem', textAlign: 'center', fontSize: 12, color: 'var(--text-secondary)' }}>
              Outcome
            </th>
          </tr>
        </thead>
        <tbody>
          {data.metrics.map((m) => (
            <MetricRow key={m.metric} row={m} tickers={data.tickers} />
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-secondary)' }}>
        Rules version: {data.rulesVersion} · * = winner
      </div>
    </div>
  );
}

function CompareInner() {
  const searchParams = useSearchParams();
  const tickersParam = searchParams.get('tickers') ?? '';
  const initialTickers = tickersParam
    ? tickersParam.split(',').map((t) => t.trim().toUpperCase())
    : [];

  const [input, setInput] = useState(initialTickers.join(', '));
  const [tickers, setTickers] = useState<string[]>(initialTickers);

  const { data, isLoading, error } = useComparison(tickers);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = input
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    if (parsed.length >= 2 && parsed.length <= 3) {
      setTickers(parsed);
    }
  }

  return (
    <>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8, marginBottom: '1.5rem' }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="WEGE3, ITUB4, RENT3"
          style={{
            flex: 1,
            padding: '0.5rem 0.75rem',
            background: 'rgba(148,163,184,0.08)',
            border: '1px solid rgba(148,163,184,0.2)',
            borderRadius: 6,
            color: 'var(--text-primary, #e2e8f0)',
            fontSize: 14,
          }}
        />
        <button
          type="submit"
          style={{
            padding: '0.5rem 1rem',
            background: 'var(--accent-gold, #fbbf24)',
            color: '#0a0e1a',
            border: 'none',
            borderRadius: 6,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Compare
        </button>
      </form>

      {isLoading && <p style={{ color: 'var(--text-secondary)' }}>Carregando...</p>}
      {error && <p style={{ color: '#f87171' }}>Erro ao comparar ativos.</p>}
      {data && <ComparisonResult data={data} />}
      {!data && !isLoading && tickers.length < 2 && (
        <p style={{ color: 'var(--text-secondary)' }}>
          Digite 2 ou 3 tickers separados por virgula para comparar.
        </p>
      )}
    </>
  );
}

export default function ComparePage() {
  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <Link href="/ranking" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
          ← Ranking
        </Link>
        <h1>Compare Assets</h1>
      </header>
      <div style={{ padding: '1.5rem' }}>
        <Suspense fallback={<p style={{ color: 'var(--text-secondary)' }}>Loading...</p>}>
          <CompareInner />
        </Suspense>
      </div>
    </div>
  );
}
