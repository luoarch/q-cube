import { z } from 'zod';

import { uuidSchema } from './_shared.js';
import { assetDetailSchema } from './asset.js';
import {
  dataCompletenessSchema,
  flagsSchema,
  issuerClassificationSchema,
  periodValueSchema,
  scoreReliabilitySchema,
} from './refiner.js';

export const refinerSummarySchema = z.object({
  earningsQualityScore: z.number().nullable(),
  safetyScore: z.number().nullable(),
  operatingConsistencyScore: z.number().nullable(),
  capitalDisciplineScore: z.number().nullable(),
  refinementScore: z.number().nullable(),
  adjustedRank: z.number().nullable(),
  flags: flagsSchema,
  scoreReliability: scoreReliabilitySchema,
  issuerClassification: issuerClassificationSchema,
  dataCompleteness: dataCompletenessSchema,
});

export const trendSeriesSchema = z.object({
  metric: z.string(),
  values: z.array(periodValueSchema),
});

export const companyIntelligenceSchema = z.object({
  ticker: z.string(),
  issuerId: uuidSchema.nullable(),
  baseDetail: assetDetailSchema,
  refiner: refinerSummarySchema.nullable(),
  trends: z.array(trendSeriesSchema),
  flags: flagsSchema.nullable(),
  classification: issuerClassificationSchema.nullable(),
  scoreReliability: scoreReliabilitySchema.nullable(),
});

export type CompanyIntelligence = z.infer<typeof companyIntelligenceSchema>;
