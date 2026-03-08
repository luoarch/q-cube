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

export const portfolioSchema = z.object({
  totalValue: z.number(),
  totalReturn: z.number(),
  holdings: z.array(portfolioHoldingSchema),
  equityCurve: z.array(z.object({ time: z.string(), value: z.number() })).nullable(),
  factorTilt: z.array(portfolioFactorSchema),
});

export type PortfolioData = z.infer<typeof portfolioSchema>;
