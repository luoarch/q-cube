import { z } from 'zod';

import { uuidSchema } from './_shared.js';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const thesisBucketSchema = z.enum([
  'A_DIRECT',
  'B_INDIRECT',
  'C_NEUTRAL',
  'D_FRAGILE',
]);
export type ThesisBucket = z.infer<typeof thesisBucketSchema>;

export const scoreSourceTypeSchema = z.enum([
  'QUANTITATIVE',
  'SECTOR_PROXY',
  'RUBRIC_MANUAL',
  'AI_ASSISTED',
  'DERIVED',
  'DEFAULT',
]);
export type ScoreSourceType = z.infer<typeof scoreSourceTypeSchema>;

export const scoreConfidenceSchema = z.enum(['high', 'medium', 'low']);
export type ScoreConfidence = z.infer<typeof scoreConfidenceSchema>;

// ---------------------------------------------------------------------------
// Provenance
// ---------------------------------------------------------------------------

export const scoreProvenanceSchema = z.object({
  sourceType: scoreSourceTypeSchema,
  sourceVersion: z.string(),
  assessedAt: z.string(),
  assessedBy: z.string().nullable(),
  confidence: scoreConfidenceSchema,
  evidenceRef: z.string().nullable(),
});
export type ScoreProvenance = z.infer<typeof scoreProvenanceSchema>;

export const dimensionProvenanceSchema = z.record(
  z.string(),
  scoreProvenanceSchema,
);
export type DimensionProvenance = z.infer<typeof dimensionProvenanceSchema>;

// ---------------------------------------------------------------------------
// Eligibility
// ---------------------------------------------------------------------------

export const baseEligibilitySchema = z.object({
  eligibleForPlan2: z.boolean(),
  failedReasons: z.array(z.string()),
  passedCoreScreening: z.boolean(),
  hasValidFinancials: z.boolean(),
  interestCoverage: z.number().nullable(),
  debtToEbitda: z.number().nullable(),
});
export type BaseEligibility = z.infer<typeof baseEligibilitySchema>;

// ---------------------------------------------------------------------------
// Vectors
// ---------------------------------------------------------------------------

export const opportunityVectorSchema = z.object({
  directCommodityExposureScore: z.number().min(0).max(100),
  indirectCommodityExposureScore: z.number().min(0).max(100),
  exportFxLeverageScore: z.number().min(0).max(100),
  finalCommodityAffinityScore: z.number().min(0).max(100),
});
export type OpportunityVector = z.infer<typeof opportunityVectorSchema>;

export const fragilityVectorSchema = z.object({
  refinancingStressScore: z.number().min(0).max(100),
  usdDebtExposureScore: z.number().min(0).max(100),
  usdImportDependenceScore: z.number().min(0).max(100),
  usdRevenueOffsetScore: z.number().min(0).max(100),
  finalDollarFragilityScore: z.number().min(0).max(100),
});
export type FragilityVector = z.infer<typeof fragilityVectorSchema>;

// ---------------------------------------------------------------------------
// Feature schemas (F1 draft → B2 complete)
// ---------------------------------------------------------------------------

export const plan2FeatureDraftSchema = z.object({
  issuerId: uuidSchema,
  ticker: z.string(),
  // eligibility inputs
  passedCoreScreening: z.boolean(),
  hasValidFinancials: z.boolean(),
  interestCoverage: z.number().nullable(),
  debtToEbitda: z.number().nullable(),
  coreRankPercentile: z.number().min(0).max(100),
  // opportunity (nullable — may not be computed yet)
  directCommodityExposureScore: z.number().min(0).max(100).nullable(),
  indirectCommodityExposureScore: z.number().min(0).max(100).nullable(),
  exportFxLeverageScore: z.number().min(0).max(100).nullable(),
  // fragility (nullable — may not be computed yet)
  refinancingStressScore: z.number().min(0).max(100).nullable(),
  usdDebtExposureScore: z.number().min(0).max(100).nullable(),
  usdImportDependenceScore: z.number().min(0).max(100).nullable(),
  usdRevenueOffsetScore: z.number().min(0).max(100).nullable(),
  // provenance per dimension
  provenance: dimensionProvenanceSchema,
});
export type Plan2FeatureDraft = z.infer<typeof plan2FeatureDraftSchema>;

export const plan2FeatureInputSchema = z.object({
  issuerId: uuidSchema,
  ticker: z.string(),
  // eligibility inputs
  passedCoreScreening: z.boolean(),
  hasValidFinancials: z.boolean(),
  interestCoverage: z.number().nullable(),
  debtToEbitda: z.number().nullable(),
  coreRankPercentile: z.number().min(0).max(100),
  // opportunity (required — B2 ensures all present)
  directCommodityExposureScore: z.number().min(0).max(100),
  indirectCommodityExposureScore: z.number().min(0).max(100),
  exportFxLeverageScore: z.number().min(0).max(100),
  // fragility (required)
  refinancingStressScore: z.number().min(0).max(100),
  usdDebtExposureScore: z.number().min(0).max(100),
  usdImportDependenceScore: z.number().min(0).max(100),
  usdRevenueOffsetScore: z.number().min(0).max(100),
  // provenance per dimension
  provenance: dimensionProvenanceSchema,
});
export type Plan2FeatureInput = z.infer<typeof plan2FeatureInputSchema>;

// ---------------------------------------------------------------------------
// Explanation
// ---------------------------------------------------------------------------

export const plan2ExplanationSchema = z.object({
  ticker: z.string(),
  bucket: thesisBucketSchema,
  thesisRankScore: z.number().min(0).max(100),
  positives: z.array(z.string()),
  negatives: z.array(z.string()),
  summary: z.string(),
});
export type Plan2Explanation = z.infer<typeof plan2ExplanationSchema>;

// ---------------------------------------------------------------------------
// Ranking snapshot (full internal record per issuer)
// ---------------------------------------------------------------------------

export const plan2RankingSnapshotSchema = z.object({
  issuerId: uuidSchema,
  ticker: z.string(),
  companyName: z.string(),
  sector: z.string().nullable(),
  eligible: z.boolean(),
  eligibility: baseEligibilitySchema,
  // vectors (nullable if ineligible)
  opportunityVector: opportunityVectorSchema.nullable(),
  fragilityVector: fragilityVectorSchema.nullable(),
  // ranking (nullable if ineligible)
  bucket: thesisBucketSchema.nullable(),
  thesisRankScore: z.number().min(0).max(100).nullable(),
  thesisRank: z.number().int().nullable(),
  baseCoreScore: z.number().min(0).max(100),
  // explanation
  explanation: plan2ExplanationSchema.nullable(),
  // provenance
  provenance: dimensionProvenanceSchema,
});
export type Plan2RankingSnapshot = z.infer<typeof plan2RankingSnapshotSchema>;

// ---------------------------------------------------------------------------
// Evidence quality
// ---------------------------------------------------------------------------

export const evidenceQualitySchema = z.enum([
  'HIGH_EVIDENCE',
  'MIXED_EVIDENCE',
  'LOW_EVIDENCE',
]);
export type EvidenceQuality = z.infer<typeof evidenceQualitySchema>;

// ---------------------------------------------------------------------------
// API response item (flat, for the ranking list)
// ---------------------------------------------------------------------------

export const plan2RankResponseItemSchema = z.object({
  ticker: z.string(),
  companyName: z.string(),
  sector: z.string().nullable(),
  bucket: thesisBucketSchema,
  baseCoreScore: z.number(),
  finalCommodityAffinityScore: z.number(),
  finalDollarFragilityScore: z.number(),
  thesisRankScore: z.number(),
  thesisRank: z.number().int(),
  evidenceQuality: evidenceQualitySchema,
  positives: z.array(z.string()),
  negatives: z.array(z.string()),
});
export type Plan2RankResponseItem = z.infer<typeof plan2RankResponseItemSchema>;

// ---------------------------------------------------------------------------
// API run metadata (returned alongside ranking)
// ---------------------------------------------------------------------------

export const plan2RunMetadataSchema = z.object({
  runId: z.string(),
  asOfDate: z.string(),
  thesisConfigVersion: z.string(),
  pipelineVersion: z.string(),
  totalEligible: z.number().int(),
  totalIneligible: z.number().int(),
  bucketDistribution: z.record(z.string(), z.number().int()),
  coverageSummary: z.object({
    highPct: z.number(),
    mixedPct: z.number(),
    lowPct: z.number(),
  }),
});
export type Plan2RunMetadata = z.infer<typeof plan2RunMetadataSchema>;

export const plan2RankingResponseSchema = z.object({
  meta: plan2RunMetadataSchema,
  data: z.array(plan2RankResponseItemSchema),
});
export type Plan2RankingResponse = z.infer<typeof plan2RankingResponseSchema>;

// ---------------------------------------------------------------------------
// Breakdown response (per-ticker detail)
// ---------------------------------------------------------------------------

export const dimensionBreakdownItemSchema = z.object({
  key: z.string(),
  label: z.string(),
  score: z.number(),
  weight: z.number(),
  weightedContribution: z.number(),
  sourceType: scoreSourceTypeSchema,
  sourceVersion: z.string(),
  confidence: scoreConfidenceSchema,
  evidenceRef: z.string().nullable(),
  isDefault: z.boolean(),
  isDerived: z.boolean(),
});
export type DimensionBreakdownItem = z.infer<typeof dimensionBreakdownItemSchema>;

// ---------------------------------------------------------------------------
// Rubric scores (manual/AI dimension scoring)
// ---------------------------------------------------------------------------

export const rubricScoreInputSchema = z.object({
  issuerId: uuidSchema,
  dimensionKey: z.string(),
  score: z.number().min(0).max(100),
  sourceType: z.enum(['RUBRIC_MANUAL', 'AI_ASSISTED']),
  sourceVersion: z.string(),
  confidence: scoreConfidenceSchema,
  evidenceRef: z.string().nullable().optional(),
  rationale: z.string().nullable().optional(),
  assessedBy: z.string().nullable().optional(),
  assessedAt: z.string(),
});
export type RubricScoreInput = z.infer<typeof rubricScoreInputSchema>;

export const rubricScoreResponseSchema = z.object({
  id: uuidSchema,
  issuerId: uuidSchema,
  dimensionKey: z.string(),
  score: z.number(),
  sourceType: z.string(),
  sourceVersion: z.string(),
  confidence: z.string(),
  evidenceRef: z.string().nullable(),
  rationale: z.string().nullable(),
  assessedBy: z.string().nullable(),
  assessedAt: z.string(),
  supersededAt: z.string().nullable(),
  createdAt: z.string(),
});
export type RubricScoreResponse = z.infer<typeof rubricScoreResponseSchema>;

// ---------------------------------------------------------------------------
// Breakdown response (per-ticker detail)
// ---------------------------------------------------------------------------

export const plan2BreakdownResponseSchema = z.object({
  ticker: z.string(),
  companyName: z.string(),
  sector: z.string().nullable(),
  bucket: thesisBucketSchema,
  thesisRank: z.number().int(),
  thesisRankScore: z.number(),
  evidenceQuality: evidenceQualitySchema,
  // Score breakdown
  baseCoreScore: z.number(),
  finalCommodityAffinityScore: z.number(),
  finalDollarFragilityScore: z.number(),
  // Per-dimension detail
  opportunityDimensions: z.array(dimensionBreakdownItemSchema),
  fragilityDimensions: z.array(dimensionBreakdownItemSchema),
  // Explanation
  positives: z.array(z.string()),
  negatives: z.array(z.string()),
  summary: z.string(),
  // Run context
  runId: z.string(),
  asOfDate: z.string(),
  thesisConfigVersion: z.string(),
  pipelineVersion: z.string(),
});
export type Plan2BreakdownResponse = z.infer<typeof plan2BreakdownResponseSchema>;
