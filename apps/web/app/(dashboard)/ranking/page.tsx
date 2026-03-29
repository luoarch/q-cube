'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import { useRanking } from '../../../src/hooks/api/useRanking';
import { StrategyContextBanner } from '../../../src/components/StrategyContextBanner';
import { RankingDisclaimer } from '../../../src/components/MethodologicalDisclaimer';
import { ProvenanceFooter } from '../../../src/components/ProvenanceFooter';
import { useThesisRanking } from '../../../src/hooks/api/useThesisRanking';

import type {
  RankingItem,
  Plan2RankResponseItem,
  Plan2RunMetadata,
  ThesisBucket,
  EvidenceQuality,
} from '@q3/shared-contracts';

type RankingMode = 'core' | 'thesis';

const QUALITY_COLORS: Record<string, string> = {
  high: '#22c55e',
  medium: '#fbbf24',
  low: '#ef4444',
};

const BUCKET_COLORS: Record<ThesisBucket, string> = {
  A_DIRECT: '#22c55e',
  B_INDIRECT: '#3b82f6',
  C_NEUTRAL: '#94a3b8',
  D_FRAGILE: '#ef4444',
};

const BUCKET_LABELS: Record<ThesisBucket, string> = {
  A_DIRECT: 'A Direct',
  B_INDIRECT: 'B Indirect',
  C_NEUTRAL: 'C Neutral',
  D_FRAGILE: 'D Fragile',
};

const EVIDENCE_COLORS: Record<EvidenceQuality, string> = {
  HIGH_EVIDENCE: '#22c55e',
  MIXED_EVIDENCE: '#fbbf24',
  LOW_EVIDENCE: '#ef4444',
};

const EVIDENCE_LABELS: Record<EvidenceQuality, string> = {
  HIGH_EVIDENCE: 'HIGH',
  MIXED_EVIDENCE: 'MIXED',
  LOW_EVIDENCE: 'LOW',
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

function formatScore(n: number): string {
  return n.toFixed(1);
}

// ---------------------------------------------------------------------------
// Chip components
// ---------------------------------------------------------------------------

function BucketChip({ bucket }: { bucket: ThesisBucket }) {
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 10,
        background: `${BUCKET_COLORS[bucket]}18`,
        color: BUCKET_COLORS[bucket],
      }}
    >
      {BUCKET_LABELS[bucket]}
    </span>
  );
}

function EvidenceChip({ quality }: { quality: EvidenceQuality }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '1px 6px',
        borderRadius: 8,
        background: `${EVIDENCE_COLORS[quality]}14`,
        color: EVIDENCE_COLORS[quality],
        letterSpacing: '0.03em',
      }}
    >
      {EVIDENCE_LABELS[quality]}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Run metadata banner
// ---------------------------------------------------------------------------

function ThesisMetaBanner({ meta }: { meta: Plan2RunMetadata }) {
  const shortRunId = meta.runId.slice(0, 8);
  return (
    <div
      style={{
        padding: '0.5rem 1.25rem',
        borderBottom: '1px solid var(--border-color)',
        background: 'rgba(251, 191, 36, 0.05)',
        fontSize: 12,
        color: 'var(--text-secondary)',
        display: 'flex',
        alignItems: 'center',
        gap: '1.25rem',
        flexWrap: 'wrap',
      }}
    >
      <span style={{ fontWeight: 600, color: 'var(--accent-gold)' }}>Thesis Mode</span>
      <span>as_of: <b>{meta.asOfDate}</b></span>
      <span>run: <b>{shortRunId}</b></span>
      <span>config: <b>{meta.thesisConfigVersion}</b></span>
      <span>pipeline: <b>{meta.pipelineVersion}</b></span>
      <span style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: '1rem' }}>
        evidence:
        {' '}<span style={{ color: '#22c55e' }}>{meta.coverageSummary.highPct}% HIGH</span>
        {' '}<span style={{ color: '#fbbf24' }}>{meta.coverageSummary.mixedPct}% MIXED</span>
        {' '}<span style={{ color: '#ef4444' }}>{meta.coverageSummary.lowPct}% LOW</span>
      </span>
      <span style={{ fontSize: 11, color: 'var(--text-secondary)', opacity: 0.7 }}>
        D_FRAGILE limitado no MVP
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Core Ranking Table
// ---------------------------------------------------------------------------

const MODEL_COLORS: Record<string, string> = {
  NPY_ROC: '#22c55e',
  EY_ROC: '#94a3b8',
};

function ModelChip({ model }: { model: string }) {
  const color = MODEL_COLORS[model] ?? '#94a3b8';
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '1px 6px',
        borderRadius: 8,
        background: `${color}18`,
        color,
        letterSpacing: '0.03em',
      }}
    >
      {model === 'NPY_ROC' ? 'NPY+ROC' : 'EY+ROC'}
    </span>
  );
}

function CoreRankingTable({ items, showModel }: { items: RankingItem[]; showModel?: boolean }) {
  return (
    <table className="ranking-table">
      <thead>
        <tr>
          <th style={{ width: 50, textAlign: 'center' }}>#</th>
          <th>Ticker</th>
          <th>Empresa</th>
          <th>Setor</th>
          {showModel && <th style={{ textAlign: 'center' }}>Modelo</th>}
          <th style={{ textAlign: 'right' }}>NPY</th>
          <th style={{ textAlign: 'right' }}>ROIC</th>
          <th style={{ textAlign: 'right' }}>Market Cap</th>
          <th style={{ textAlign: 'center' }}>Quality</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.ticker} style={{ opacity: item.investabilityStatus === 'partially_evaluated' ? 0.6 : 1 }}>
            <td style={{ textAlign: 'center', color: 'var(--text-secondary)', fontWeight: 600 }}>
              {item.rankWithinModel}
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
            {showModel && (
              <td style={{ textAlign: 'center' }}>
                <ModelChip model={item.modelFamily} />
              </td>
            )}
            <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
              {item.netPayoutYield != null ? formatPercent(item.netPayoutYield) : '—'}
            </td>
            <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
              {formatPercent(item.returnOnCapital)}
            </td>
            <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
              {item.marketCap > 0 ? formatNumber(item.marketCap) : '—'}
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
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// Thesis Ranking Table
// ---------------------------------------------------------------------------

function ThesisRankingTable({ items }: { items: Plan2RankResponseItem[] }) {
  return (
    <table className="ranking-table">
      <thead>
        <tr>
          <th style={{ width: 50, textAlign: 'center' }}>#</th>
          <th>Ticker</th>
          <th>Empresa</th>
          <th>Setor</th>
          <th style={{ textAlign: 'center' }}>Bucket</th>
          <th style={{ textAlign: 'right' }}>Thesis Score</th>
          <th style={{ textAlign: 'right' }}>Commodity</th>
          <th style={{ textAlign: 'right' }}>Fragility</th>
          <th style={{ textAlign: 'right' }}>Core Base</th>
          <th style={{ textAlign: 'center' }}>Evidence</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.ticker}>
            <td style={{ textAlign: 'center', color: 'var(--text-secondary)', fontWeight: 600 }}>
              {item.thesisRank}
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
              {item.companyName}
            </td>
            <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{item.sector}</td>
            <td style={{ textAlign: 'center' }}>
              <BucketChip bucket={item.bucket} />
            </td>
            <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13, fontWeight: 600 }}>
              {formatScore(item.thesisRankScore)}
            </td>
            <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
              {formatScore(item.finalCommodityAffinityScore)}
            </td>
            <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13 }}>
              {formatScore(item.finalDollarFragilityScore)}
            </td>
            <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 13, color: 'var(--text-secondary)' }}>
              {formatScore(item.baseCoreScore)}
            </td>
            <td style={{ textAlign: 'center' }}>
              <EvidenceChip quality={item.evidenceQuality} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function RankingPage() {
  const [mode, setMode] = useState<RankingMode>('core');
  const coreQuery = useRanking();
  const thesisQuery = useThesisRanking();

  const [sectorFilter, setSectorFilter] = useState<string | null>(null);
  const [qualityFilter, setQualityFilter] = useState<string | null>(null);
  const [bucketFilter, setBucketFilter] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const coreItems = useMemo(() => coreQuery.data?.primaryRanking ?? [], [coreQuery.data]);
  const secondaryItems = useMemo(() => coreQuery.data?.secondaryRanking ?? [], [coreQuery.data]);
  const coreSummary = coreQuery.data?.summary ?? null;
  const thesisData = thesisQuery.data;
  const thesisItems = useMemo(() => thesisData?.data ?? [], [thesisData]);
  const thesisMeta = thesisData?.meta ?? null;

  const isLoading = mode === 'core' ? coreQuery.isLoading : thesisQuery.isLoading;
  const isError = mode === 'thesis' && thesisQuery.isError;

  // Core filters
  const sectors = useMemo(
    () => [...new Set(coreItems.map((it) => it.sector))].sort(),
    [coreItems],
  );

  const filteredCore = useMemo(() => {
    let result = coreItems;
    if (sectorFilter) result = result.filter((it) => it.sector === sectorFilter);
    if (qualityFilter) result = result.filter((it) => it.quality === qualityFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (it) => it.ticker.toLowerCase().includes(q) || it.name.toLowerCase().includes(q),
      );
    }
    return result;
  }, [coreItems, sectorFilter, qualityFilter, search]);

  const filteredThesis = useMemo(() => {
    let result = thesisItems;
    if (bucketFilter) result = result.filter((it) => it.bucket === bucketFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (it) => it.ticker.toLowerCase().includes(q) || it.companyName.toLowerCase().includes(q),
      );
    }
    return result;
  }, [thesisItems, bucketFilter, search]);

  const displayCount = mode === 'core' ? filteredCore.length : filteredThesis.length;
  const totalCount = mode === 'core' ? coreItems.length : thesisItems.length;

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <h1>Ranking</h1>
          <div
            style={{
              display: 'inline-flex',
              borderRadius: 8,
              border: '1px solid var(--border-color)',
              overflow: 'hidden',
            }}
          >
            <button
              onClick={() => setMode('core')}
              style={{
                padding: '4px 14px',
                fontSize: 12,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: mode === 'core' ? 'var(--accent-gold)' : 'transparent',
                color: mode === 'core' ? '#000' : 'var(--text-secondary)',
              }}
            >
              Core
            </button>
            <button
              onClick={() => setMode('thesis')}
              style={{
                padding: '4px 14px',
                fontSize: 12,
                fontWeight: 600,
                border: 'none',
                borderLeft: '1px solid var(--border-color)',
                cursor: 'pointer',
                background: mode === 'thesis' ? 'var(--accent-gold)' : 'transparent',
                color: mode === 'thesis' ? '#000' : 'var(--text-secondary)',
              }}
            >
              Thesis
            </button>
          </div>
        </div>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          {displayCount} de {totalCount} ativos
        </span>
      </header>

      {/* Strategy context + methodology disclaimer */}
      <StrategyContextBanner />
      <RankingDisclaimer />

      {/* Thesis mode metadata banner */}
      {mode === 'thesis' && thesisMeta && <ThesisMetaBanner meta={thesisMeta} />}

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
        {mode === 'core' && (
          <>
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
          </>
        )}
        {mode === 'thesis' && (
          <select
            value={bucketFilter ?? ''}
            onChange={(e) => setBucketFilter(e.target.value || null)}
            style={{
              padding: '6px 12px',
              background: 'var(--bg-canvas)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 6,
              fontSize: 13,
            }}
          >
            <option value="">Todos os buckets</option>
            <option value="A_DIRECT">A Direct</option>
            <option value="B_INDIRECT">B Indirect</option>
            <option value="C_NEUTRAL">C Neutral</option>
            <option value="D_FRAGILE">D Fragile</option>
          </select>
        )}
      </div>

      {/* Summary banner */}
      {mode === 'core' && coreSummary && (
        <div
          style={{
            padding: '0.5rem 1.25rem',
            borderBottom: '1px solid var(--border-color)',
            background: 'rgba(34, 197, 94, 0.04)',
            fontSize: 12,
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '1.25rem',
          }}
        >
          <span>
            <span style={{ color: '#22c55e', fontWeight: 600 }}>{coreSummary.primaryCount}</span> NPY+ROC
          </span>
          <span>
            <span style={{ color: '#94a3b8', fontWeight: 600 }}>{coreSummary.secondaryCount}</span> EY+ROC
          </span>
          <span style={{ opacity: 0.7 }}>
            {coreSummary.totalUniverse} universo total
          </span>
          {coreSummary.missingDataBreakdown && Object.keys(coreSummary.missingDataBreakdown).length > 0 && (
            <span style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: '1rem', opacity: 0.7 }}>
              dados faltantes: {Object.entries(coreSummary.missingDataBreakdown).map(([k, v]) => `${k.replace('missing_', '')}=${v}`).join(', ')}
            </span>
          )}
        </div>
      )}

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {isLoading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Carregando ranking...
          </div>
        ) : isError ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Nenhuma run do Plano 2 encontrada. Execute uma run primeiro.
          </div>
        ) : mode === 'core' ? (
          <>
            <CoreRankingTable items={filteredCore} />
            {secondaryItems.length > 0 && (
              <>
                <div style={{ padding: '1rem 1.25rem 0.5rem', borderTop: '2px solid var(--border-color)' }}>
                  <h3 style={{ fontSize: 14, color: 'var(--text-secondary)', margin: 0, fontWeight: 600 }}>
                    Avaliacao parcial ({secondaryItems.length} ativos — EY+ROC, sem NPY)
                  </h3>
                  <p style={{ fontSize: 11, color: 'var(--text-secondary)', margin: '4px 0 0', opacity: 0.7 }}>
                    Estes ativos nao possuem dados completos de payout. Rankeados com formula alternativa. Apenas para pesquisa.
                  </p>
                </div>
                <CoreRankingTable items={secondaryItems} showModel />
              </>
            )}
          </>
        ) : (
          <ThesisRankingTable items={filteredThesis} />
        )}
      </div>
    </div>
  );
}
