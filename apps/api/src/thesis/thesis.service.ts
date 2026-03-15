import { Inject, Injectable } from '@nestjs/common';
import {
  plan2RankResponseItemSchema,
  plan2RankingResponseSchema,
  plan2BreakdownResponseSchema,
} from '@q3/shared-contracts';
import { eq, desc, and, isNotNull, sql } from 'drizzle-orm';

import { CacheService } from '../common/cache.service.js';
import { DB } from '../database/database.constants.js';
import { plan2Runs, plan2ThesisScores, issuers, securities } from '../db/schema.js';

import type {
  Plan2RankingResponse,
  Plan2BreakdownResponse,
  EvidenceQuality,
  DimensionBreakdownItem,
} from '@q3/shared-contracts';
import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

const THESIS_CACHE_TTL = 300; // 5 minutes

const HIGH_SOURCE_TYPES = new Set(['QUANTITATIVE', 'RUBRIC_MANUAL']);

// Mirrors q3_quant_engine/thesis/config.py
const OPPORTUNITY_WEIGHTS = {
  direct_commodity_exposure: { weight: 0.50, label: 'Direct Commodity Exposure' },
  indirect_commodity_exposure: { weight: 0.30, label: 'Indirect Commodity Exposure' },
  export_fx_leverage: { weight: 0.20, label: 'Export / FX Leverage' },
} as const;

const FRAGILITY_WEIGHTS = {
  refinancing_stress: { weight: 0.30, label: 'Refinancing Stress' },
  usd_debt_exposure: { weight: 0.30, label: 'USD Debt Exposure' },
  usd_import_dependence: { weight: 0.20, label: 'USD Import Dependence' },
  usd_revenue_offset: { weight: 0.20, label: 'USD Revenue Offset (inverted)' },
} as const;

interface ProvenanceEntry {
  source_type?: string;
  sourceType?: string;
  source_version?: string;
  sourceVersion?: string;
  confidence?: string;
  evidence_ref?: string | null;
  evidenceRef?: string | null;
  assessed_at?: string;
  assessedAt?: string;
}

interface FeatureInputJson {
  provenance?: Record<string, ProvenanceEntry>;
  input?: {
    provenance?: Record<string, ProvenanceEntry>;
    direct_commodity_exposure_score?: number;
    indirect_commodity_exposure_score?: number;
    export_fx_leverage_score?: number;
    refinancing_stress_score?: number;
    usd_debt_exposure_score?: number;
    usd_import_dependence_score?: number;
    usd_revenue_offset_score?: number;
    core_rank_percentile?: number;
  };
}

function deriveEvidenceQuality(
  provenance: Record<string, ProvenanceEntry> | null | undefined,
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

function getProvenance(provenance: Record<string, ProvenanceEntry> | null | undefined, key: string): ProvenanceEntry {
  if (!provenance) return {};
  // Try both snake_case key variants
  return provenance[key] ?? provenance[`${key}_score`] ?? {};
}

function buildDimensionItem(
  key: string,
  label: string,
  score: number,
  weight: number,
  prov: ProvenanceEntry,
): DimensionBreakdownItem {
  const sourceType = (prov.source_type ?? prov.sourceType ?? 'DEFAULT') as DimensionBreakdownItem['sourceType'];
  return {
    key,
    label,
    score,
    weight,
    weightedContribution: Math.round(score * weight * 10) / 10,
    sourceType,
    sourceVersion: prov.source_version ?? prov.sourceVersion ?? 'unknown',
    confidence: (prov.confidence ?? 'low') as DimensionBreakdownItem['confidence'],
    evidenceRef: prov.evidence_ref ?? prov.evidenceRef ?? null,
    isDefault: sourceType === 'DEFAULT',
    isDerived: sourceType === 'DERIVED',
  };
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

  async getBreakdown(tenantId: string, ticker: string): Promise<Plan2BreakdownResponse | null> {
    // Find latest completed plan2 run
    const latestRun = await this.db
      .select({
        id: plan2Runs.id,
        asOfDate: plan2Runs.asOfDate,
        thesisConfigVersion: plan2Runs.thesisConfigVersion,
        pipelineVersion: plan2Runs.pipelineVersion,
      })
      .from(plan2Runs)
      .where(and(eq(plan2Runs.tenantId, tenantId), eq(plan2Runs.status, 'completed')))
      .orderBy(desc(plan2Runs.createdAt))
      .limit(1)
      .then((rows) => rows[0]);

    if (!latestRun) return null;

    // Find score for this ticker
    const row = await this.db
      .select({
        ticker: securities.ticker,
        companyName: sql<string>`coalesce(${issuers.tradeName}, ${issuers.legalName})`,
        sector: issuers.sector,
        bucket: plan2ThesisScores.bucket,
        finalCommodityAffinityScore: plan2ThesisScores.finalCommodityAffinityScore,
        finalDollarFragilityScore: plan2ThesisScores.finalDollarFragilityScore,
        thesisRankScore: plan2ThesisScores.thesisRankScore,
        thesisRank: plan2ThesisScores.thesisRank,
        explanationJson: plan2ThesisScores.explanationJson,
        featureInputJson: plan2ThesisScores.featureInputJson,
        directCommodityExposureScore: plan2ThesisScores.directCommodityExposureScore,
        indirectCommodityExposureScore: plan2ThesisScores.indirectCommodityExposureScore,
        exportFxLeverageScore: plan2ThesisScores.exportFxLeverageScore,
        refinancingStressScore: plan2ThesisScores.refinancingStressScore,
        usdDebtExposureScore: plan2ThesisScores.usdDebtExposureScore,
        usdImportDependenceScore: plan2ThesisScores.usdImportDependenceScore,
        usdRevenueOffsetScore: plan2ThesisScores.usdRevenueOffsetScore,
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
          eq(securities.ticker, ticker),
        ),
      )
      .limit(1)
      .then((rows) => rows[0]);

    if (!row || !row.bucket) return null;

    const featureInput = row.featureInputJson as FeatureInputJson | null;
    const provenance = featureInput?.provenance ?? featureInput?.input?.provenance ?? null;
    const input = featureInput?.input;
    const evidenceQuality = deriveEvidenceQuality(provenance);

    // Build per-dimension scores from DB columns (authoritative) with provenance from JSON
    const directScore = Number(row.directCommodityExposureScore) || 0;
    const indirectScore = Number(row.indirectCommodityExposureScore) || 0;
    const exportFxScore = Number(row.exportFxLeverageScore) || 0;
    const refinancingScore = Number(row.refinancingStressScore) || 0;
    const usdDebtScore = Number(row.usdDebtExposureScore) || 0;
    const usdImportScore = Number(row.usdImportDependenceScore) || 0;
    const usdRevenueScore = Number(row.usdRevenueOffsetScore) || 0;

    const baseCoreScore = Number(input?.core_rank_percentile) || 0;

    const opportunityDimensions: DimensionBreakdownItem[] = [
      buildDimensionItem(
        'direct_commodity_exposure', OPPORTUNITY_WEIGHTS.direct_commodity_exposure.label,
        directScore, OPPORTUNITY_WEIGHTS.direct_commodity_exposure.weight,
        getProvenance(provenance, 'direct_commodity_exposure'),
      ),
      buildDimensionItem(
        'indirect_commodity_exposure', OPPORTUNITY_WEIGHTS.indirect_commodity_exposure.label,
        indirectScore, OPPORTUNITY_WEIGHTS.indirect_commodity_exposure.weight,
        getProvenance(provenance, 'indirect_commodity_exposure'),
      ),
      buildDimensionItem(
        'export_fx_leverage', OPPORTUNITY_WEIGHTS.export_fx_leverage.label,
        exportFxScore, OPPORTUNITY_WEIGHTS.export_fx_leverage.weight,
        getProvenance(provenance, 'export_fx_leverage'),
      ),
    ];

    const fragilityDimensions: DimensionBreakdownItem[] = [
      buildDimensionItem(
        'refinancing_stress', FRAGILITY_WEIGHTS.refinancing_stress.label,
        refinancingScore, FRAGILITY_WEIGHTS.refinancing_stress.weight,
        getProvenance(provenance, 'refinancing_stress'),
      ),
      buildDimensionItem(
        'usd_debt_exposure', FRAGILITY_WEIGHTS.usd_debt_exposure.label,
        usdDebtScore, FRAGILITY_WEIGHTS.usd_debt_exposure.weight,
        getProvenance(provenance, 'usd_debt_exposure'),
      ),
      buildDimensionItem(
        'usd_import_dependence', FRAGILITY_WEIGHTS.usd_import_dependence.label,
        usdImportScore, FRAGILITY_WEIGHTS.usd_import_dependence.weight,
        getProvenance(provenance, 'usd_import_dependence'),
      ),
      buildDimensionItem(
        'usd_revenue_offset', FRAGILITY_WEIGHTS.usd_revenue_offset.label,
        usdRevenueScore, FRAGILITY_WEIGHTS.usd_revenue_offset.weight,
        getProvenance(provenance, 'usd_revenue_offset'),
      ),
    ];

    const explanation = row.explanationJson as {
      positives?: string[];
      negatives?: string[];
      summary?: string;
    } | null;

    return plan2BreakdownResponseSchema.parse({
      ticker: row.ticker,
      companyName: row.companyName ?? row.ticker,
      sector: row.sector ?? null,
      bucket: row.bucket,
      thesisRank: row.thesisRank ?? 0,
      thesisRankScore: Number(row.thesisRankScore) || 0,
      evidenceQuality,
      baseCoreScore,
      finalCommodityAffinityScore: Number(row.finalCommodityAffinityScore) || 0,
      finalDollarFragilityScore: Number(row.finalDollarFragilityScore) || 0,
      opportunityDimensions,
      fragilityDimensions,
      positives: explanation?.positives ?? [],
      negatives: explanation?.negatives ?? [],
      summary: explanation?.summary ?? '',
      runId: String(latestRun.id),
      asOfDate: String(latestRun.asOfDate),
      thesisConfigVersion: latestRun.thesisConfigVersion,
      pipelineVersion: latestRun.pipelineVersion,
    });
  }

  private async loadLatestRanking(tenantId: string): Promise<Plan2RankingResponse | null> {
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

    let highCount = 0;
    let mixedCount = 0;
    let lowCount = 0;

    const data = rows.map((row) => {
      const explanation = row.explanationJson as {
        positives?: string[];
        negatives?: string[];
      } | null;

      const featureInput = row.featureInputJson as FeatureInputJson | null;
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
