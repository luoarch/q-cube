import { Inject, Injectable, Logger } from '@nestjs/common';
import {
  type RefinementResult,
  refinementResultSchema,
  refinementResultsResponseSchema,
} from '@q3/shared-contracts';
import { and, eq } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';
import { refinementResults } from '../db/schema.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

@Injectable()
export class RefinerService {
  private readonly logger = new Logger(RefinerService.name);

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
  ) {}

  async getByRunId(strategyRunId: string, tenantId: string) {
    const rows = await this.db
      .select()
      .from(refinementResults)
      .where(
        and(
          eq(refinementResults.strategyRunId, strategyRunId),
          eq(refinementResults.tenantId, tenantId),
        ),
      )
      .orderBy(refinementResults.adjustedRank);

    const results = rows.map((row) => this.mapRow(row));

    return refinementResultsResponseSchema.parse({
      strategyRunId,
      results,
      formulaVersion: results[0]?.formulaVersion ?? 1,
      weightsVersion: results[0]?.weightsVersion ?? 1,
    });
  }

  async getByRunIdAndTicker(strategyRunId: string, ticker: string, tenantId: string) {
    const [row] = await this.db
      .select()
      .from(refinementResults)
      .where(
        and(
          eq(refinementResults.strategyRunId, strategyRunId),
          eq(refinementResults.tenantId, tenantId),
          eq(refinementResults.ticker, ticker),
        ),
      )
      .limit(1);

    if (!row) {
      return null;
    }

    return refinementResultSchema.parse(this.mapRow(row));
  }

  private mapRow(row: typeof refinementResults.$inferSelect): RefinementResult {
    return {
      id: row.id,
      strategyRunId: row.strategyRunId,
      tenantId: row.tenantId,
      issuerId: row.issuerId,
      ticker: row.ticker,
      baseRank: row.baseRank,
      earningsQualityScore: row.earningsQualityScore ? Number(row.earningsQualityScore) : null,
      safetyScore: row.safetyScore ? Number(row.safetyScore) : null,
      operatingConsistencyScore: row.operatingConsistencyScore
        ? Number(row.operatingConsistencyScore)
        : null,
      capitalDisciplineScore: row.capitalDisciplineScore
        ? Number(row.capitalDisciplineScore)
        : null,
      refinementScore: row.refinementScore ? Number(row.refinementScore) : null,
      adjustedScore: row.adjustedScore ? Number(row.adjustedScore) : null,
      adjustedRank: row.adjustedRank,
      flags: (row.flagsJson as { red: string[]; strength: string[] }) ?? {
        red: [],
        strength: [],
      },
      trendData: (row.trendDataJson as Record<string, { referenceDate: string; value: number | null }[]>) ?? {},
      scoringDetails: (row.scoringDetailsJson as Record<string, unknown>) ?? {},
      dataCompleteness: (row.dataCompletenessJson as {
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
      },
      scoreReliability: (row.scoreReliability as 'high' | 'medium' | 'low' | 'unavailable') ?? 'unavailable',
      issuerClassification: (row.issuerClassification as 'non_financial' | 'bank' | 'insurer' | 'utility' | 'holding') ?? 'non_financial',
      formulaVersion: row.formulaVersion,
      weightsVersion: row.weightsVersion,
      createdAt: row.createdAt.toISOString(),
    } satisfies RefinementResult;
  }
}
