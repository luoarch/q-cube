'use client';

/**
 * D2 — Language Guardrails
 *
 * Centralized disclaimers and contextual notes that enforce honest
 * communication across all surfaces. Every surface that shows strategy
 * results, rankings, or scores must include appropriate context.
 *
 * Principle: the system describes what it computed, never what the user
 * should do. Rankings are orderings, not recommendations.
 */

/**
 * Compact disclaimer bar for surfaces showing ranking/scoring results.
 * Appears below headers, above data.
 */
export function RankingDisclaimer() {
  return (
    <div
      style={{
        padding: '0.3rem 1.25rem',
        fontSize: 11,
        color: 'var(--text-secondary)',
        borderBottom: '1px solid var(--border-color)',
        background: 'var(--bg-surface)',
        lineHeight: 1.4,
      }}
    >
      Ranking quantitativo baseado em EY + ROC (Greenblatt). Ordenação por fórmula, não recomendação de investimento.
      Nenhuma estratégia deste sistema foi empiricamente promovida.
    </div>
  );
}

/**
 * Disclaimer for portfolio/holdings surfaces.
 */
export function PortfolioDisclaimer() {
  return (
    <div
      style={{
        padding: '0.3rem 1.25rem',
        fontSize: 11,
        color: 'var(--text-secondary)',
        borderBottom: '1px solid var(--border-color)',
        background: 'var(--bg-surface)',
        lineHeight: 1.4,
      }}
    >
      Composição derivada do último ranking executado. Não constitui carteira recomendada.
      Estratégia subjacente não promovida — resultados de pesquisa, não evidência de performance.
    </div>
  );
}

/**
 * Disclaimer for backtest result surfaces.
 */
export function BacktestDisclaimer() {
  return (
    <div
      style={{
        padding: '0.3rem 1.25rem',
        fontSize: 11,
        color: 'var(--text-secondary)',
        borderBottom: '1px solid var(--border-color)',
        background: 'var(--bg-surface)',
        lineHeight: 1.4,
      }}
    >
      Backtest com dados PIT e custos reais (BRAZIL_REALISTIC). Resultados passados não garantem performance futura.
      Universo congelado (frozen policy), benchmark price-only (sem reinvestimento de dividendos).
    </div>
  );
}

/**
 * Disclaimer for the home page hero area.
 */
export function HomeDisclaimer() {
  return (
    <div
      style={{
        fontSize: 10,
        color: 'rgba(148,163,184,0.7)',
        marginTop: '0.5rem',
        lineHeight: 1.3,
      }}
    >
      Ferramenta quantitativa de screening. Ordenações por fórmula, não recomendações.
    </div>
  );
}

/**
 * Tooltip text for specific UI elements that might over-claim.
 */
export const GUARDRAIL_TOOLTIPS = {
  compositeScore:
    'Score composto percentil (ROIC + EY + ROE + margens). Métrica relativa ao universo, não indicador absoluto de qualidade.',
  topRank:
    'Posição no ranking quantitativo por fórmula (EY + ROC). Ordenação, não recomendação.',
  factorAnalysis:
    'Fatores percentil relativos ao universo Core. Indicam posição relativa, não qualidade absoluta.',
  dividendYield:
    'DY calculado via TTM CVM filings / market cap Yahoo. Dual-trail: exact (vendor) e free-source (CVM proxy).',
  thesisBucket:
    'Classificação do Plan 2 (commodity affinity + dollar fragility). Baseada em rubrics, não em backtest.',
} as const;
