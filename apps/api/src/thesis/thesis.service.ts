import { Inject, Injectable, Logger } from '@nestjs/common';
import {
  plan2RankResponseItemSchema,
  plan2RankingResponseSchema,
  plan2BreakdownResponseSchema,
} from '@q3/shared-contracts';
import { eq, desc, and, isNull, isNotNull, sql } from 'drizzle-orm';

import { CacheService } from '../common/cache.service.js';
import { DB } from '../database/database.constants.js';
import { plan2Runs, plan2ThesisScores, plan2RubricScores, issuers, securities } from '../db/schema.js';

import type {
  Plan2RankingResponse,
  Plan2BreakdownResponse,
  RubricScoreInput,
  RubricScoreResponse,
  EvidenceQuality,
  DimensionBreakdownItem,
} from '@q3/shared-contracts';
import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

const AI_ASSISTANT_URL = process.env.AI_ASSISTANT_URL ?? 'http://localhost:8400';
const QUANT_ENGINE_URL = process.env.QUANT_ENGINE_URL ?? 'http://localhost:8100';
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

export interface RubricSuggestion {
  suggestionId: string;
  issuerId: string;
  ticker: string;
  dimensionKey: string;
  suggestedScore: number;
  confidence: string;
  rationale: string;
  evidenceRef: string;
  keySignals: string[];
  uncertaintyFactors: string[];
  modelUsed: string;
  promptVersion: string;
  costUsd: number;
}

@Injectable()
export class ThesisService {
  private readonly logger = new Logger(ThesisService.name);

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

  async getRubrics(
    _tenantId: string,
    ticker: string,
  ): Promise<{ issuerId: string; ticker: string; rubrics: RubricScoreResponse[] } | null> {
    // Resolve ticker → issuerId (issuers are global CVM data, tenant scoped by AuthGuard)
    const issuer = await this.db
      .select({ issuerId: issuers.id })
      .from(issuers)
      .innerJoin(securities, and(eq(securities.issuerId, issuers.id), eq(securities.isPrimary, true)))
      .where(eq(securities.ticker, ticker))
      .limit(1)
      .then((rows) => rows[0]);

    if (!issuer) return null;

    const rows = await this.db
      .select()
      .from(plan2RubricScores)
      .where(and(eq(plan2RubricScores.issuerId, issuer.issuerId), isNull(plan2RubricScores.supersededAt)))
      .orderBy(plan2RubricScores.dimensionKey);

    return {
      issuerId: issuer.issuerId,
      ticker,
      rubrics: rows.map((r) => ({
        id: r.id,
        issuerId: r.issuerId,
        dimensionKey: r.dimensionKey,
        score: Number(r.score),
        sourceType: r.sourceType,
        sourceVersion: r.sourceVersion,
        confidence: r.confidence,
        evidenceRef: r.evidenceRef,
        rationale: r.rationale,
        assessedBy: r.assessedBy,
        assessedAt: String(r.assessedAt),
        supersededAt: r.supersededAt ? r.supersededAt.toISOString() : null,
        createdAt: r.createdAt.toISOString(),
      })),
    };
  }

  async upsertRubric(_tenantId: string, input: RubricScoreInput): Promise<RubricScoreResponse> {
    // Verify issuer exists (issuers are global CVM data, tenant scoped by AuthGuard)
    const issuer = await this.db
      .select({ id: issuers.id })
      .from(issuers)
      .where(eq(issuers.id, input.issuerId))
      .limit(1)
      .then((rows) => rows[0]);

    if (!issuer) {
      throw new Error(`Issuer ${input.issuerId} not found`);
    }

    // Supersede existing active score for this dimension
    await this.db
      .update(plan2RubricScores)
      .set({ supersededAt: new Date() })
      .where(
        and(
          eq(plan2RubricScores.issuerId, input.issuerId),
          eq(plan2RubricScores.dimensionKey, input.dimensionKey),
          isNull(plan2RubricScores.supersededAt),
        ),
      );

    // Insert new active score
    const rows = await this.db
      .insert(plan2RubricScores)
      .values({
        issuerId: input.issuerId,
        dimensionKey: input.dimensionKey,
        score: String(input.score),
        sourceType: input.sourceType,
        sourceVersion: input.sourceVersion,
        confidence: input.confidence,
        evidenceRef: input.evidenceRef ?? null,
        rationale: input.rationale ?? null,
        assessedBy: input.assessedBy ?? null,
        assessedAt: input.assessedAt,
      })
      .returning();

    const row = rows[0]!;

    return {
      id: row.id,
      issuerId: row.issuerId,
      dimensionKey: row.dimensionKey,
      score: Number(row.score),
      sourceType: row.sourceType,
      sourceVersion: row.sourceVersion,
      confidence: row.confidence,
      evidenceRef: row.evidenceRef,
      rationale: row.rationale,
      assessedBy: row.assessedBy,
      assessedAt: String(row.assessedAt),
      supersededAt: row.supersededAt ? row.supersededAt.toISOString() : null,
      createdAt: row.createdAt.toISOString(),
    };
  }

  async suggestRubric(tenantId: string, ticker: string, dimensionKey = 'usd_debt_exposure'): Promise<RubricSuggestion> {
    const res = await fetch(`${AI_ASSISTANT_URL}/rubric/suggest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker,
        tenant_id: tenantId,
        dimension_key: dimensionKey,
      }),
    });

    if (!res.ok) {
      const errorText = await res.text();
      this.logger.warn(`Rubric suggest proxy failed: ${res.status} ${errorText}`);
      throw new Error(`AI suggestion failed: ${res.status}`);
    }

    const data = (await res.json()) as {
      suggestion_id: string;
      issuer_id: string;
      ticker: string;
      dimension_key: string;
      suggested_score: number;
      confidence: string;
      rationale: string;
      evidence_ref: string;
      key_signals: string[];
      uncertainty_factors: string[];
      model_used: string;
      prompt_version: string;
      cost_usd: number;
    };

    return {
      suggestionId: data.suggestion_id,
      issuerId: data.issuer_id,
      ticker: data.ticker,
      dimensionKey: data.dimension_key,
      suggestedScore: data.suggested_score,
      confidence: data.confidence,
      rationale: data.rationale,
      evidenceRef: data.evidence_ref,
      keySignals: data.key_signals,
      uncertaintyFactors: data.uncertainty_factors,
      modelUsed: data.model_used,
      promptVersion: data.prompt_version,
      costUsd: data.cost_usd,
    };
  }

  // ---------------------------------------------------------------------------
  // F3.2 — Monitoring proxy (quant-engine)
  // ---------------------------------------------------------------------------

  private async getLatestRunId(tenantId: string): Promise<string | null> {
    const row = await this.db
      .select({ id: plan2Runs.id })
      .from(plan2Runs)
      .where(and(eq(plan2Runs.tenantId, tenantId), eq(plan2Runs.status, 'completed')))
      .orderBy(desc(plan2Runs.createdAt))
      .limit(1)
      .then((rows) => rows[0]);
    return row ? String(row.id) : null;
  }

  async getMonitoringSummary(tenantId: string): Promise<unknown> {
    const runId = await this.getLatestRunId(tenantId);
    if (!runId) return null;

    const res = await fetch(`${QUANT_ENGINE_URL}/plan2/runs/${runId}/monitoring`);
    if (!res.ok) {
      this.logger.warn(`Monitoring proxy failed: ${res.status}`);
      throw new Error(`Monitoring request failed: ${res.status}`);
    }
    return res.json();
  }

  async getDrift(tenantId: string, vsRunId?: string): Promise<unknown> {
    const runId = await this.getLatestRunId(tenantId);
    if (!runId) return null;

    const params = vsRunId ? `?vs_run_id=${vsRunId}` : '';
    const res = await fetch(`${QUANT_ENGINE_URL}/plan2/runs/${runId}/drift${params}`);
    if (!res.ok) {
      this.logger.warn(`Drift proxy failed: ${res.status}`);
      throw new Error(`Drift request failed: ${res.status}`);
    }
    return res.json();
  }

  async getRubricAging(staleDays = 30): Promise<unknown> {
    const res = await fetch(`${QUANT_ENGINE_URL}/plan2/rubrics/aging?stale_days=${staleDays}`);
    if (!res.ok) {
      this.logger.warn(`Rubric aging proxy failed: ${res.status}`);
      throw new Error(`Rubric aging request failed: ${res.status}`);
    }
    return res.json();
  }

  async getReviewQueue(staleDays = 30): Promise<unknown> {
    const res = await fetch(`${QUANT_ENGINE_URL}/plan2/rubrics/review-queue?stale_days=${staleDays}`);
    if (!res.ok) {
      this.logger.warn(`Review queue proxy failed: ${res.status}`);
      throw new Error(`Review queue request failed: ${res.status}`);
    }
    return res.json();
  }

  async getAlerts(tenantId: string, staleDays = 30): Promise<unknown> {
    const runId = await this.getLatestRunId(tenantId);
    if (!runId) return null;

    const res = await fetch(`${QUANT_ENGINE_URL}/plan2/runs/${runId}/alerts?stale_days=${staleDays}`);
    if (!res.ok) {
      this.logger.warn(`Alerts proxy failed: ${res.status}`);
      throw new Error(`Alerts request failed: ${res.status}`);
    }
    return res.json();
  }
}
