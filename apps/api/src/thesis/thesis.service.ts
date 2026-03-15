import { Inject, Injectable } from '@nestjs/common';
import {
  plan2RankResponseItemSchema,
  plan2RankingResponseSchema,
} from '@q3/shared-contracts';
import { eq, desc, and, isNotNull, sql } from 'drizzle-orm';

import { CacheService } from '../common/cache.service.js';
import { DB } from '../database/database.constants.js';
import { plan2Runs, plan2ThesisScores, issuers, securities } from '../db/schema.js';

import type { Plan2RankingResponse, EvidenceQuality } from '@q3/shared-contracts';
import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

const THESIS_CACHE_TTL = 300; // 5 minutes

const HIGH_SOURCE_TYPES = new Set(['QUANTITATIVE', 'RUBRIC_MANUAL']);

function deriveEvidenceQuality(
  provenance: Record<string, { source_type?: string; sourceType?: string }> | null | undefined,
): EvidenceQuality {
  if (!provenance || typeof provenance !== 'object') return 'LOW_EVIDENCE';
  const entries = Object.values(provenance);
  if (entries.length === 0) return 'LOW_EVIDENCE';
  const total = entries.length;
  const hardCount = entries.filter(
    (p) => HIGH_SOURCE_TYPES.has(p.source_type ?? '') || HIGH_SOURCE_TYPES.has(p.sourceType ?? ''),
  ).length;
  if (hardCount / total > 0.5) return 'HIGH_EVIDENCE';
  if (hardCount > 0) return 'MIXED_EVIDENCE';
  return 'LOW_EVIDENCE';
}

@Injectable()
export class ThesisService {
  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
    private readonly cache: CacheService,
  ) {}

  async getRanking(
    tenantId: string,
    filters?: { bucket?: string | undefined; search?: string | undefined },
  ): Promise<Plan2RankingResponse | null> {
    const cacheKey = `q3:thesis-ranking:${tenantId}`;
    let cached = await this.cache.get<Plan2RankingResponse>(cacheKey);
    if (!cached) {
      cached = await this.loadLatestRanking(tenantId);
      if (cached) {
        await this.cache.set(cacheKey, cached, THESIS_CACHE_TTL);
      }
    }
    if (!cached) return null;

    let data = cached.data;
    if (filters?.bucket) {
      data = data.filter((item) => item.bucket === filters.bucket);
    }
    if (filters?.search) {
      const q = filters.search.toLowerCase();
      data = data.filter(
        (item) =>
          item.ticker.toLowerCase().includes(q) ||
          item.companyName.toLowerCase().includes(q),
      );
    }

    return { meta: cached.meta, data };
  }

  private async loadLatestRanking(tenantId: string): Promise<Plan2RankingResponse | null> {
    // Find latest completed plan2 run for this tenant
    const latestRun = await this.db
      .select({
        id: plan2Runs.id,
        asOfDate: plan2Runs.asOfDate,
        thesisConfigVersion: plan2Runs.thesisConfigVersion,
        pipelineVersion: plan2Runs.pipelineVersion,
        totalEligible: plan2Runs.totalEligible,
        totalIneligible: plan2Runs.totalIneligible,
        bucketDistributionJson: plan2Runs.bucketDistributionJson,
      })
      .from(plan2Runs)
      .where(and(eq(plan2Runs.tenantId, tenantId), eq(plan2Runs.status, 'completed')))
      .orderBy(desc(plan2Runs.createdAt))
      .limit(1)
      .then((rows) => rows[0]);

    if (!latestRun) return null;

    // Load eligible scores with ticker from securities
    const rows = await this.db
      .select({
        ticker: securities.ticker,
        companyName: sql<string>`coalesce(${issuers.tradeName}, ${issuers.legalName})`,
        sector: issuers.sector,
        bucket: plan2ThesisScores.bucket,
        baseCoreScore: sql<string>`coalesce(
          (${plan2ThesisScores.featureInputJson}->>'coreRankPercentile')::text,
          (${plan2ThesisScores.featureInputJson}->'input'->>'core_rank_percentile')::text,
          (${plan2ThesisScores.featureInputJson}->'draft'->'draft'->>'core_rank_percentile')::text,
          '0'
        )`,
        finalCommodityAffinityScore: plan2ThesisScores.finalCommodityAffinityScore,
        finalDollarFragilityScore: plan2ThesisScores.finalDollarFragilityScore,
        thesisRankScore: plan2ThesisScores.thesisRankScore,
        thesisRank: plan2ThesisScores.thesisRank,
        explanationJson: plan2ThesisScores.explanationJson,
        featureInputJson: plan2ThesisScores.featureInputJson,
      })
      .from(plan2ThesisScores)
      .innerJoin(issuers, eq(issuers.id, plan2ThesisScores.issuerId))
      .innerJoin(
        securities,
        and(eq(securities.issuerId, issuers.id), eq(securities.isPrimary, true)),
      )
      .where(
        and(
          eq(plan2ThesisScores.plan2RunId, latestRun.id),
          eq(plan2ThesisScores.eligible, true),
          isNotNull(plan2ThesisScores.bucket),
        ),
      )
      .orderBy(plan2ThesisScores.thesisRank);

    // Compute per-row evidence quality and coverage summary
    let highCount = 0;
    let mixedCount = 0;
    let lowCount = 0;

    const data = rows.map((row) => {
      const explanation = row.explanationJson as {
        positives?: string[];
        negatives?: string[];
      } | null;

      const featureInput = row.featureInputJson as {
        provenance?: Record<string, { source_type?: string; sourceType?: string }>;
        input?: { provenance?: Record<string, { source_type?: string; sourceType?: string }> };
      } | null;

      const provenance = featureInput?.provenance ?? featureInput?.input?.provenance ?? null;
      const evidenceQuality = deriveEvidenceQuality(provenance);

      if (evidenceQuality === 'HIGH_EVIDENCE') highCount++;
      else if (evidenceQuality === 'MIXED_EVIDENCE') mixedCount++;
      else lowCount++;

      return plan2RankResponseItemSchema.parse({
        ticker: row.ticker,
        companyName: row.companyName ?? row.ticker,
        sector: row.sector ?? null,
        bucket: row.bucket,
        baseCoreScore: Number(row.baseCoreScore) || 0,
        finalCommodityAffinityScore: Number(row.finalCommodityAffinityScore) || 0,
        finalDollarFragilityScore: Number(row.finalDollarFragilityScore) || 0,
        thesisRankScore: Number(row.thesisRankScore) || 0,
        thesisRank: row.thesisRank ?? 0,
        evidenceQuality,
        positives: explanation?.positives ?? [],
        negatives: explanation?.negatives ?? [],
      });
    });

    const total = data.length || 1;
    const bucketDist = (latestRun.bucketDistributionJson ?? {}) as Record<string, number>;

    return plan2RankingResponseSchema.parse({
      meta: {
        runId: String(latestRun.id),
        asOfDate: String(latestRun.asOfDate),
        thesisConfigVersion: latestRun.thesisConfigVersion,
        pipelineVersion: latestRun.pipelineVersion,
        totalEligible: latestRun.totalEligible,
        totalIneligible: latestRun.totalIneligible,
        bucketDistribution: bucketDist,
        coverageSummary: {
          highPct: Math.round((highCount / total) * 1000) / 10,
          mixedPct: Math.round((mixedCount / total) * 1000) / 10,
          lowPct: Math.round((lowCount / total) * 1000) / 10,
        },
      },
      data,
    });
  }
}
