import { Inject, Injectable, Logger } from '@nestjs/common';
import { type ComparisonMatrix, comparisonMatrixSchema } from '@q3/shared-contracts';
import { and, eq, inArray, sql } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';
import {
  computedMetrics,
  issuers,
  refinementResults,
  securities,
  strategyRuns,
} from '../db/schema.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

@Injectable()
export class ComparisonService {
  private readonly logger = new Logger(ComparisonService.name);

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
  ) {}

  async compare(tickers: string[], tenantId: string): Promise<ComparisonMatrix> {
    // Resolve tickers to issuer IDs
    const secRows = await this.db
      .select({
        ticker: securities.ticker,
        issuerId: securities.issuerId,
        sector: issuers.sector,
        subsector: issuers.subsector,
      })
      .from(securities)
      .innerJoin(issuers, eq(securities.issuerId, issuers.id))
      .where(
        and(
          inArray(securities.ticker, tickers),
          sql`${securities.validTo} IS NULL`,
        ),
      );

    if (secRows.length < 2) {
      throw new Error(`Need at least 2 valid tickers, found ${secRows.length}`);
    }

    const issuerIds = secRows.map((r) => r.issuerId);
    const tickerMap = Object.fromEntries(secRows.map((r) => [r.issuerId, r.ticker]));

    // Load latest computed metrics for each issuer
    const metricsRows = await this.db
      .select({
        issuerId: computedMetrics.issuerId,
        metricCode: computedMetrics.metricCode,
        value: computedMetrics.value,
        referenceDate: computedMetrics.referenceDate,
      })
      .from(computedMetrics)
      .where(inArray(computedMetrics.issuerId, issuerIds));

    // Group by issuer -> metric -> values
    const issuerMetrics: Record<string, Record<string, number[]>> = {};
    for (const row of metricsRows) {
      const iid = row.issuerId;
      if (!issuerMetrics[iid]) issuerMetrics[iid] = {};
      const bucket = issuerMetrics[iid]!;
      if (!bucket[row.metricCode]) bucket[row.metricCode] = [];
      if (row.value !== null) {
        bucket[row.metricCode]!.push(Number(row.value));
      }
    }

    // Try to load refinement scores from latest strategy run
    const latestRun = await this.db
      .select({ id: strategyRuns.id })
      .from(strategyRuns)
      .where(eq(strategyRuns.tenantId, tenantId))
      .orderBy(sql`${strategyRuns.createdAt} DESC`)
      .limit(1);

    if (latestRun[0]) {
      const refRows = await this.db
        .select({
          issuerId: refinementResults.issuerId,
          refinementScore: refinementResults.refinementScore,
          scoreReliability: refinementResults.scoreReliability,
        })
        .from(refinementResults)
        .where(
          and(
            eq(refinementResults.strategyRunId, latestRun[0].id),
            inArray(refinementResults.issuerId, issuerIds),
          ),
        );

      for (const row of refRows) {
        if (!issuerMetrics[row.issuerId]) issuerMetrics[row.issuerId] = {};
        if (row.refinementScore !== null) {
          issuerMetrics[row.issuerId]!['refinement_score'] = [Number(row.refinementScore)];
        }
      }
    }

    // Apply comparison rules — compute with issuer IDs, then convert to ticker keys
    const rules = COMPARISON_RULES;
    const metricResults = rules.map((rule) => {
      // Compute values keyed by issuer ID internally
      const rawValues: Record<string, number | null> = {};
      for (const iid of issuerIds) {
        const series = issuerMetrics[iid]?.[rule.metric] ?? [];
        if (rule.comparisonMode === 'latest') {
          rawValues[iid] = series.length > 0 ? series[series.length - 1]! : null;
        } else if (rule.comparisonMode === 'avg_3p') {
          const last3 = series.slice(-3);
          rawValues[iid] = last3.length > 0 ? last3.reduce((a, b) => a + b, 0) / last3.length : null;
        } else if (rule.comparisonMode === 'stdev_3p') {
          const last3 = series.slice(-3);
          if (last3.length < 2) {
            rawValues[iid] = null;
          } else {
            const mean = last3.reduce((a, b) => a + b, 0) / last3.length;
            const variance = last3.reduce((a, b) => a + (b - mean) ** 2, 0) / (last3.length - 1);
            rawValues[iid] = Math.sqrt(variance);
          }
        }
      }

      const { winner: winnerIid, outcome, margin } = determineWinner(rawValues, rule);

      // Convert keys from issuer ID → ticker for frontend consumption
      const values: Record<string, number | null> = {};
      for (const iid of issuerIds) {
        values[tickerMap[iid]!] = rawValues[iid] ?? null;
      }
      const winner = winnerIid ? (tickerMap[winnerIid] ?? null) : null;

      return {
        metric: rule.metric,
        direction: rule.direction,
        comparisonMode: rule.comparisonMode,
        tolerance: rule.tolerance,
        values,
        winner,
        outcome,
        margin,
      };
    });

    // Build summaries — keyed by ticker
    const tickerList = issuerIds.map((iid) => tickerMap[iid]!);
    const summaries = issuerIds.map((iid) => {
      const ticker = tickerMap[iid]!;
      return {
        issuerId: iid,
        ticker,
        wins: metricResults.filter((m) => m.winner === ticker && m.outcome === 'win').length,
        ties: metricResults.filter((m) => m.outcome === 'tie').length,
        losses: metricResults.filter(
          (m) => m.outcome === 'win' && m.winner !== ticker && m.winner !== null,
        ).length,
        inconclusive: metricResults.filter((m) => m.outcome === 'inconclusive').length,
      };
    });

    return comparisonMatrixSchema.parse({
      issuerIds,
      tickers: tickerList,
      metrics: metricResults,
      summaries,
      rulesVersion: 1,
      dataReliability: Object.fromEntries(
        issuerIds.map((iid) => [tickerMap[iid]!, issuerMetrics[iid] ? 'medium' : 'unavailable']),
      ),
    });
  }
}

// Comparison rules (mirrored from Python for SSOT — versioned)
type ComparisonRule = {
  metric: string;
  direction: string;
  comparisonMode: string;
  tolerance: number;
};

const COMPARISON_RULES: ComparisonRule[] = [
  { metric: 'earnings_yield', direction: 'higher_better', comparisonMode: 'latest', tolerance: 0.005 },
  { metric: 'roic', direction: 'higher_better', comparisonMode: 'latest', tolerance: 0.01 },
  { metric: 'roe', direction: 'higher_better', comparisonMode: 'latest', tolerance: 0.01 },
  { metric: 'gross_margin', direction: 'higher_better', comparisonMode: 'avg_3p', tolerance: 0.01 },
  { metric: 'ebit_margin', direction: 'higher_better', comparisonMode: 'avg_3p', tolerance: 0.01 },
  { metric: 'net_margin', direction: 'higher_better', comparisonMode: 'avg_3p', tolerance: 0.005 },
  { metric: 'cash_conversion', direction: 'higher_better', comparisonMode: 'avg_3p', tolerance: 0.05 },
  { metric: 'debt_to_ebitda', direction: 'lower_better', comparisonMode: 'latest', tolerance: 0.3 },
  { metric: 'interest_coverage', direction: 'higher_better', comparisonMode: 'latest', tolerance: 1.0 },
  { metric: 'margin_stability', direction: 'lower_stdev_better', comparisonMode: 'stdev_3p', tolerance: 0.005 },
  { metric: 'refinement_score', direction: 'higher_better', comparisonMode: 'latest', tolerance: 0.02 },
];

function determineWinner(
  values: Record<string, number | null>,
  rule: ComparisonRule,
): { winner: string | null; outcome: string; margin: number | null } {
  const valid = Object.entries(values).filter(([, v]) => v !== null) as [string, number][];

  if (valid.length === 0) return { winner: null, outcome: 'inconclusive', margin: null };
  if (valid.length === 1) return { winner: valid[0]![0], outcome: 'win', margin: null };

  const sorted =
    rule.direction === 'lower_better' || rule.direction === 'lower_stdev_better'
      ? valid.sort((a, b) => a[1] - b[1])
      : valid.sort((a, b) => b[1] - a[1]);

  const first = sorted[0]!;
  const second = sorted[1]!;
  const margin = Math.abs(first[1] - second[1]);
  if (margin < rule.tolerance) return { winner: null, outcome: 'tie', margin };

  return { winner: first[0], outcome: 'win', margin };
}
