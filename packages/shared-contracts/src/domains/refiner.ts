import { z } from 'zod';

import { uuidSchema } from './_shared.js';

export const scoreReliabilitySchema = z.enum(['high', 'medium', 'low', 'unavailable']);
export type ScoreReliability = z.infer<typeof scoreReliabilitySchema>;

export const issuerClassificationSchema = z.enum([
  'non_financial',
  'bank',
  'insurer',
  'utility',
  'holding',
]);
export type IssuerClassification = z.infer<typeof issuerClassificationSchema>;

export const periodValueSchema = z.object({
  referenceDate: z.string(),
  value: z.number().nullable(),
});

export const dataCompletenessSchema = z.object({
  periodsAvailable: z.number(),
  metricsAvailable: z.number(),
  metricsExpected: z.number(),
  completenessRatio: z.number(),
  missingCritical: z.array(z.string()),
  proxyUsed: z.array(z.string()),
});

export const flagsSchema = z.object({
  red: z.array(z.string()),
  strength: z.array(z.string()),
});

export const refinementResultSchema = z.object({
  id: uuidSchema,
  strategyRunId: uuidSchema,
  tenantId: uuidSchema,
  issuerId: uuidSchema,
  ticker: z.string(),
  baseRank: z.number(),
  earningsQualityScore: z.number().nullable(),
  safetyScore: z.number().nullable(),
  operatingConsistencyScore: z.number().nullable(),
  capitalDisciplineScore: z.number().nullable(),
  refinementScore: z.number().nullable(),
  adjustedScore: z.number().nullable(),
  adjustedRank: z.number().nullable(),
  flags: flagsSchema,
  trendData: z.record(z.string(), z.array(periodValueSchema)),
  scoringDetails: z.record(z.string(), z.unknown()),
  dataCompleteness: dataCompletenessSchema,
  scoreReliability: scoreReliabilitySchema,
  issuerClassification: issuerClassificationSchema,
  formulaVersion: z.number(),
  weightsVersion: z.number(),
  createdAt: z.string(),
});

export type RefinementResult = z.infer<typeof refinementResultSchema>;

export const refinementResultsResponseSchema = z.object({
  strategyRunId: uuidSchema,
  results: z.array(refinementResultSchema),
  formulaVersion: z.number(),
  weightsVersion: z.number(),
});

export type RefinementResultsResponse = z.infer<typeof refinementResultsResponseSchema>;

export const refinementSingleResponseSchema = refinementResultSchema;
export type RefinementSingleResponse = z.infer<typeof refinementSingleResponseSchema>;
