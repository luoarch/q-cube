import { z } from 'zod';

export const portfolioHoldingSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  weight: z.number(),
  value: z.number(),
  return: z.number(),
  sector: z.string(),
});

export const portfolioFactorSchema = z.object({
  name: z.string(),
  value: z.number(),
  max: z.number(),
});

export const dataProvenanceSchema = z.object({
  source: z.string(),
  runId: z.string().nullable().optional(),
  strategy: z.string().nullable().optional(),
  runDate: z.string().nullable().optional(),
  asOfDate: z.string().nullable().optional(),
  topN: z.number().nullable().optional(),
  universePolicy: z.string().optional(),
  dataSource: z.string().optional(),
});

export const portfolioSchema = z.object({
  totalValue: z.number(),
  totalReturn: z.number(),
  holdings: z.array(portfolioHoldingSchema),
  equityCurve: z.array(z.object({ time: z.string(), value: z.number() })).nullable(),
  factorTilt: z.array(portfolioFactorSchema),
  provenance: dataProvenanceSchema.nullable().optional(),
});

export type DataProvenance = z.infer<typeof dataProvenanceSchema>;

export type PortfolioData = z.infer<typeof portfolioSchema>;
