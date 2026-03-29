import { z } from 'zod';

import { dataProvenanceSchema } from './portfolio.js';

// --- Missing data enum (cause-based, no redundant missing_npy) ---

export const missingDataEnum = z.enum([
  'missing_dividend_yield',
  'missing_nby',
  'missing_roc',
  'missing_quality_signal',
  'partial_financials',
]);

// --- Ranking item (new split-model schema) ---

export const rankingItemSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  sector: z.string(),
  modelFamily: z.enum(['NPY_ROC', 'EY_ROC']),
  investabilityStatus: z.enum(['fully_evaluated', 'partially_evaluated']),
  rankWithinModel: z.number(),
  missingData: z.array(missingDataEnum),
  earningsYield: z.number(),
  returnOnCapital: z.number(),
  netPayoutYield: z.number().nullable(),
  marketCap: z.number(),
  price: z.number().nullable(),
  change: z.number().nullable(),
  quality: z.enum(['high', 'medium', 'low']),
  liquidity: z.enum(['high', 'medium', 'low']),
  // compositeScore is comparable ONLY within the same modelFamily.
  // Never use to order a merged list.
  compositeScore: z.number().nullable(),
});

// --- Summary ---

export const missingSummarySchema = z.record(z.string(), z.number());

export const rankingSummarySchema = z.object({
  primaryCount: z.number(),
  secondaryCount: z.number(),
  totalUniverse: z.number(),
  missingDataBreakdown: missingSummarySchema,
});

// --- Split-model response (no pagination — D1) ---

export const splitRankingResponseSchema = z.object({
  primaryRanking: z.array(rankingItemSchema),
  secondaryRanking: z.array(rankingItemSchema),
  summary: rankingSummarySchema,
});

// --- Legacy compat (will be removed) ---

export const paginationMetaSchema = z.object({
  page: z.number(),
  limit: z.number(),
  total: z.number(),
  totalPages: z.number(),
});

export const paginatedRankingSchema = z.object({
  data: z.array(rankingItemSchema),
  meta: paginationMetaSchema,
  provenance: dataProvenanceSchema.nullable().optional(),
});

export type MissingData = z.infer<typeof missingDataEnum>;
export type RankingItem = z.infer<typeof rankingItemSchema>;
export type RankingSummary = z.infer<typeof rankingSummarySchema>;
export type SplitRankingResponse = z.infer<typeof splitRankingResponseSchema>;
export type PaginationMeta = z.infer<typeof paginationMetaSchema>;
export type PaginatedRanking = z.infer<typeof paginatedRankingSchema>;
