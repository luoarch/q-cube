import { Inject, Injectable, Logger, NotFoundException } from '@nestjs/common';
import {
  type CompanyIntelligence,
  companyIntelligenceSchema,
} from '@q3/shared-contracts';
import { and, desc, eq, inArray, sql } from 'drizzle-orm';

import { AssetService } from '../asset/asset.service.js';
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

/** Metrics for which we load 3-period trend data. */
const TREND_METRICS = [
  'roic',
  'roe',
  'earnings_yield',
  'gross_margin',
  'ebit_margin',
  'net_margin',
  'cash_conversion',
  'debt_to_ebitda',
  'ebitda',
  'enterprise_value',
  'net_debt',
] as const;

@Injectable()
export class IntelligenceService {
  private readonly logger = new Logger(IntelligenceService.name);

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
    private readonly assetService: AssetService,
  ) {}

  async getByTicker(ticker: string, tenantId: string): Promise<CompanyIntelligence> {
    // 1. Resolve ticker to issuer
    const secRows = await this.db
      .select({
        issuerId: securities.issuerId,
        sector: issuers.sector,
        subsector: issuers.subsector,
      })
      .from(securities)
      .innerJoin(issuers, eq(securities.issuerId, issuers.id))
      .where(
        and(
          eq(securities.ticker, ticker),
          sql`${securities.validTo} IS NULL`,
        ),
      )
      .limit(1);

    const sec = secRows[0];
    if (!sec) {
      throw new NotFoundException(`Ticker not found: ${ticker}`);
    }

    const issuerId = sec.issuerId;

    // 2. Get base asset detail (percentile-ranked factors)
    const baseDetail = await this.assetService.getByTicker(ticker, tenantId);

    // 3. Load multi-period trend data from computed_metrics
    const trendRows = await this.db
      .select({
        metricCode: computedMetrics.metricCode,
        referenceDate: computedMetrics.referenceDate,
        value: computedMetrics.value,
      })
      .from(computedMetrics)
      .where(
        and(
          eq(computedMetrics.issuerId, issuerId),
          eq(computedMetrics.periodType, 'annual'),
          inArray(computedMetrics.metricCode, [...TREND_METRICS]),
        ),
      )
      .orderBy(computedMetrics.metricCode, computedMetrics.referenceDate);

    // Group by metric -> sorted period values
    const trendMap: Record<string, { referenceDate: string; value: number | null }[]> = {};
    for (const row of trendRows) {
      if (!trendMap[row.metricCode]) trendMap[row.metricCode] = [];
      trendMap[row.metricCode]!.push({
        referenceDate: row.referenceDate,
        value: row.value !== null ? Number(row.value) : null,
      });
    }

    // Keep only last 3 periods per metric
    const trends = Object.entries(trendMap).map(([metric, values]) => ({
      metric,
      values: values.slice(-3),
    }));

    // 4. Load latest refinement result (if any strategy run exists)
    let refiner: CompanyIntelligence['refiner'] = null;
    let flags: CompanyIntelligence['flags'] = null;
    let classification: CompanyIntelligence['classification'] = null;
    let scoreReliability: CompanyIntelligence['scoreReliability'] = null;

    const latestRun = await this.db
      .select({ id: strategyRuns.id })
      .from(strategyRuns)
      .where(eq(strategyRuns.tenantId, tenantId))
      .orderBy(desc(strategyRuns.createdAt))
      .limit(1);

    if (latestRun[0]) {
      const refRows = await this.db
        .select()
        .from(refinementResults)
        .where(
          and(
            eq(refinementResults.strategyRunId, latestRun[0].id),
            eq(refinementResults.issuerId, issuerId),
          ),
        )
        .limit(1);

      const ref = refRows[0];
      if (ref) {
        const flagsData = (ref.flagsJson as { red: string[]; strength: string[] }) ?? {
          red: [],
          strength: [],
        };
        const completeness = (ref.dataCompletenessJson as {
          periodsAvailable: number;
          metricsAvailable: number;
          metricsExpected: number;
          completenessRatio: number;
          missingCritical: string[];
          proxyUsed: string[];
        }) ?? {
          periodsAvailable: 0,
          metricsAvailable: 0,
          metricsExpected: 0,
          completenessRatio: 0,
          missingCritical: [],
          proxyUsed: [],
        };

        refiner = {
          earningsQualityScore: ref.earningsQualityScore ? Number(ref.earningsQualityScore) : null,
          safetyScore: ref.safetyScore ? Number(ref.safetyScore) : null,
          operatingConsistencyScore: ref.operatingConsistencyScore
            ? Number(ref.operatingConsistencyScore)
            : null,
          capitalDisciplineScore: ref.capitalDisciplineScore
            ? Number(ref.capitalDisciplineScore)
            : null,
          refinementScore: ref.refinementScore ? Number(ref.refinementScore) : null,
          adjustedRank: ref.adjustedRank,
          flags: flagsData,
          scoreReliability:
            (ref.scoreReliability as 'high' | 'medium' | 'low' | 'unavailable') ?? 'unavailable',
          issuerClassification:
            (ref.issuerClassification as
              | 'non_financial'
              | 'bank'
              | 'insurer'
              | 'utility'
              | 'holding') ?? 'non_financial',
          dataCompleteness: completeness,
        };

        flags = flagsData;
        classification = refiner.issuerClassification;
        scoreReliability = refiner.scoreReliability;
      }
    }

    return companyIntelligenceSchema.parse({
      ticker,
      issuerId,
      baseDetail,
      refiner,
      trends,
      flags,
      classification,
      scoreReliability,
    });
  }
}
