import { z } from 'zod';

export const assetFactorSchema = z.object({
  name: z.string(),
  value: z.number(),
  raw: z.number().nullable(),
  max: z.number(),
});

export const assetPricePointSchema = z.object({
  time: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
});

// ---------------------------------------------------------------------------
// Payout Yield — dual-trail analytical surface
// ---------------------------------------------------------------------------

export const exactPayoutYieldSchema = z.object({
  referenceDate: z.string(),
  dividendYield: z.number().nullable(),
  netBuybackYield: z.number().nullable(),
  netPayoutYield: z.number().nullable(),
  trail: z.literal('exact'),
});

export const freeSourcePayoutYieldSchema = z.object({
  referenceDate: z.string(),
  dividendYield: z.number().nullable(),
  nbyProxyFree: z.number().nullable(),
  npyProxyFree: z.number().nullable(),
  trail: z.literal('free-source'),
});

export const payoutYieldSchema = z.object({
  exact: exactPayoutYieldSchema.nullable(),
  freeSource: freeSourcePayoutYieldSchema.nullable(),
});

// ---------------------------------------------------------------------------
// Asset detail
// ---------------------------------------------------------------------------

export const assetDetailSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  sector: z.string(),
  price: z.number().nullable(),
  change: z.number().nullable(),
  marketCap: z.number(),
  magicFormulaRank: z.number().nullable(),
  earningsYield: z.number(),
  returnOnCapital: z.number(),
  roic: z.number(),
  roe: z.number().nullable(),
  grossMargin: z.number(),
  netMargin: z.number(),
  netDebtToEbitda: z.number(),
  dividendYield: z.number().nullable(),
  peRatio: z.number().nullable(),
  pbRatio: z.number().nullable(),
  compositeScore: z.number().nullable(),
  factors: z.array(assetFactorSchema),
  priceHistory: z.array(assetPricePointSchema).nullable(),
  payoutYield: payoutYieldSchema.nullable(),
});

export type AssetDetail = z.infer<typeof assetDetailSchema>;
export type ExactPayoutYield = z.infer<typeof exactPayoutYieldSchema>;
export type FreeSourcePayoutYield = z.infer<typeof freeSourcePayoutYieldSchema>;
export type PayoutYield = z.infer<typeof payoutYieldSchema>;
