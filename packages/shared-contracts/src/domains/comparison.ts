import { z } from 'zod';

import { scoreReliabilitySchema } from './refiner.js';

export const comparisonOutcomeSchema = z.enum(['win', 'tie', 'inconclusive']);
export type ComparisonOutcome = z.infer<typeof comparisonOutcomeSchema>;

export const metricComparisonSchema = z.object({
  metric: z.string(),
  direction: z.string(),
  comparisonMode: z.string(),
  tolerance: z.number(),
  values: z.record(z.string(), z.number().nullable()),
  winner: z.string().nullable(),
  outcome: comparisonOutcomeSchema,
  margin: z.number().nullable(),
});
export type MetricComparison = z.infer<typeof metricComparisonSchema>;

export const winnerSummarySchema = z.object({
  issuerId: z.string(),
  ticker: z.string(),
  wins: z.number(),
  ties: z.number(),
  losses: z.number(),
  inconclusive: z.number(),
});
export type WinnerSummary = z.infer<typeof winnerSummarySchema>;

export const comparisonMatrixSchema = z.object({
  issuerIds: z.array(z.string()),
  tickers: z.array(z.string()),
  metrics: z.array(metricComparisonSchema),
  summaries: z.array(winnerSummarySchema),
  rulesVersion: z.number(),
  dataReliability: z.record(z.string(), scoreReliabilitySchema),
});
export type ComparisonMatrix = z.infer<typeof comparisonMatrixSchema>;

export const compareRequestSchema = z.object({
  tickers: z
    .string()
    .transform((s) => s.split(',').map((t) => t.trim().toUpperCase()))
    .pipe(z.array(z.string().min(1)).min(2).max(3)),
});
export type CompareRequest = z.infer<typeof compareRequestSchema>;
