'use client';

import type { DataProvenance } from '@q3/shared-contracts';

/**
 * C1 — Source-specific data origin footer.
 *
 * Shows where the data on a surface came from:
 * - source (compat_view, strategy_run)
 * - strategy/config
 * - run date / reference date
 * - universe policy
 *
 * Answers: "which screening?", "which baseline?", "which data?"
 */
export function ProvenanceFooter({ provenance }: { provenance: DataProvenance | null | undefined }) {
  if (!provenance) return null;

  const parts: string[] = [];

  if (provenance.source === 'strategy_run' && provenance.runDate) {
    const d = new Date(provenance.runDate);
    parts.push(`Run: ${d.toLocaleDateString('pt-BR')} ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`);
  } else if (provenance.source === 'compat_view') {
    parts.push('Fonte: compat view (live)');
  }

  if (provenance.strategy) {
    const label = provenance.strategy
      .replace('magic_formula_', 'MF ')
      .replace('_', ' ');
    parts.push(`Estratégia: ${label}`);
  }

  if (provenance.dataSource) {
    parts.push(`Dados: ${provenance.dataSource}`);
  }

  if (provenance.universePolicy) {
    parts.push(`Universo: policy ${provenance.universePolicy}`);
  }

  if (provenance.topN) {
    parts.push(`Top ${provenance.topN}`);
  }

  if (provenance.asOfDate) {
    parts.push(`Ref: ${new Date(provenance.asOfDate).toLocaleDateString('pt-BR')}`);
  }

  if (provenance.runId) {
    parts.push(`ID: ${provenance.runId.slice(0, 8)}`);
  }

  if (parts.length === 0) return null;

  return (
    <div
      style={{
        display: 'flex',
        gap: '0.75rem',
        flexWrap: 'wrap',
        padding: '0.35rem 1.25rem',
        fontSize: 10,
        color: 'var(--text-secondary)',
        opacity: 0.7,
        borderTop: '1px solid var(--border-color)',
        fontFamily: 'monospace',
      }}
    >
      {parts.map((p, i) => (
        <span key={i}>{p}</span>
      ))}
    </div>
  );
}
