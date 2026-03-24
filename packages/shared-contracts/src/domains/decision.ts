import { z } from 'zod';

export const qualityBlockSchema = z.object({
  score: z.number(),
  label: z.string(),
  earningsQuality: z.number().nullable().optional(),
  safety: z.number().nullable().optional(),
  operatingConsistency: z.number().nullable().optional(),
  capitalDiscipline: z.number().nullable().optional(),
});

export const valuationBlockSchema = z.object({
  label: z.string().nullable(),
  valuationMethod: z.string(),
  valuationValid: z.boolean(),
  suppressionReason: z.string().optional(),
  earningsYield: z.number().nullable(),
  eyUniversePercentile: z.number().nullable().optional(),
  eySectorPercentile: z.number().nullable().optional(),
  eySectorMedian: z.number().nullable().optional(),
  sectorIssuersCount: z.number().optional(),
  sectorFallback: z.boolean().optional(),
  impliedPrice: z.number().nullable(),
  impliedValueRange: z.tuple([z.number(), z.number()]).nullable(),
  currentPrice: z.number().nullable(),
  upside: z.number().nullable(),
});

export const impliedYieldBlockSchema = z.object({
  earningsYield: z.number().nullable(),
  netPayoutYield: z.number().nullable(),
  totalYield: z.number().nullable(),
  label: z.string(),
  meetsMinimum: z.boolean(),
  minimumThreshold: z.number(),
  outlier: z.boolean(),
  outlierReason: z.string().optional(),
});

export const driverSchema = z.object({
  signal: z.string(),
  source: z.string(),
  driverType: z.enum(['structural', 'cyclical', 'historical']),
  magnitude: z.string().optional(),
  value: z.union([z.number(), z.string()]).nullable().optional(),
  valuationImpact: z.number().nullable().optional(),
});

export const riskSchema = z.object({
  signal: z.string(),
  source: z.string(),
  critical: z.boolean(),
});

export const confidenceBreakdownSchema = z.object({
  missingRefinerData: z.boolean(),
  missingThesisData: z.boolean(),
  sectorFallbackUsed: z.boolean(),
  driversCountPenalty: z.boolean(),
  valuationMissingPenalty: z.boolean(),
});

export const confidenceBlockSchema = z.object({
  score: z.number(),
  label: z.enum(['HIGH', 'MEDIUM', 'LOW']),
  dataCompleteness: z.number(),
  evidenceQuality: z.string(),
  penalties: z.array(z.string()),
  breakdown: confidenceBreakdownSchema,
});

export const decisionBlockSchema = z.object({
  status: z.enum(['APPROVED', 'BLOCKED', 'REJECTED']),
  blockReason: z.string().nullable().optional(),
  reason: z.string(),
  governanceNote: z.string().optional(),
});

export const provenanceBlockSchema = z.object({
  rankingSource: z.string().optional(),
  refinerRunId: z.string().nullable().optional(),
  thesisRunId: z.string().nullable().optional(),
  metricsReferenceDate: z.string().optional(),
  snapshotDate: z.string().optional(),
  universePolicy: z.string().optional(),
});

export const tickerDecisionSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  sector: z.string(),
  generatedAt: z.string(),
  quality: qualityBlockSchema.nullable(),
  valuation: valuationBlockSchema.nullable(),
  impliedYield: impliedYieldBlockSchema.nullable(),
  drivers: z.array(driverSchema),
  risks: z.array(riskSchema),
  confidence: confidenceBlockSchema,
  decision: decisionBlockSchema,
  provenance: provenanceBlockSchema,
});

export type TickerDecision = z.infer<typeof tickerDecisionSchema>;
