import { z } from "zod";
import { runStatusSchema, strategyTypeSchema, uuidSchema } from "./_shared.js";

export const costModelSchema = z.object({
  fixedCostPerTrade: z.number().min(0).default(0),
  proportionalCost: z.number().min(0).default(0.0005),
  slippageBps: z.number().min(0).default(10),
});

export const backtestConfigSchema = z.object({
  strategyType: strategyTypeSchema,
  startDate: z.string().date(),
  endDate: z.string().date(),
  rebalanceFreq: z.enum(["monthly", "quarterly"]).default("monthly"),
  executionLagDays: z.number().int().min(0).default(1),
  topN: z.number().int().min(1).default(20),
  equalWeight: z.boolean().default(true),
  costModel: costModelSchema.optional(),
  initialCapital: z.number().positive().default(1_000_000),
  benchmark: z.string().nullable().optional(),
});

export const backtestMetricsSchema = z.object({
  cagr: z.number(),
  volatility: z.number(),
  sharpe: z.number(),
  sortino: z.number(),
  maxDrawdown: z.number(),
  maxDrawdownDurationDays: z.number().int(),
  turnoverAvg: z.number(),
  hitRate: z.number(),
  totalCosts: z.number(),
  excessReturn: z.number().optional(),
  trackingError: z.number().optional(),
  informationRatio: z.number().optional(),
});

export const equityCurvePointSchema = z.object({
  date: z.string(),
  value: z.number(),
});

export const backtestTradeSchema = z.object({
  date: z.string(),
  ticker: z.string(),
  shares: z.number(),
  price: z.number(),
  cost: z.number(),
  side: z.enum(["buy", "sell"]),
});

export const backtestResultSchema = z.object({
  metrics: backtestMetricsSchema,
  equityCurve: z.array(equityCurvePointSchema),
  tradesCount: z.number().int(),
  rebalanceCount: z.number().int(),
});

export const createBacktestRunSchema = z.object({
  tenantId: uuidSchema,
  config: backtestConfigSchema,
});

export const backtestRunResponseSchema = z.object({
  id: uuidSchema,
  tenantId: uuidSchema,
  status: runStatusSchema,
  config: backtestConfigSchema,
  result: backtestResultSchema.nullable(),
  errorMessage: z.string().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export const walkForwardConfigSchema = z.object({
  backtestConfig: backtestConfigSchema,
  nSplits: z.number().int().min(2).default(3),
  oosMonths: z.number().int().min(1).default(12),
  embargoDays: z.number().int().min(0).default(21),
});

export const walkForwardResultSchema = z.object({
  splits: z.array(
    z.object({
      isMetrics: backtestMetricsSchema,
      oosMetrics: backtestMetricsSchema,
      isPeriod: z.object({ start: z.string(), end: z.string() }),
      oosPeriod: z.object({ start: z.string(), end: z.string() }),
    })
  ),
  isAvg: backtestMetricsSchema.partial(),
  oosAvg: backtestMetricsSchema.partial(),
  degradation: z.record(z.string(), z.number()),
});

export type CostModel = z.infer<typeof costModelSchema>;
export type BacktestConfig = z.infer<typeof backtestConfigSchema>;
export type BacktestMetrics = z.infer<typeof backtestMetricsSchema>;
export type BacktestResult = z.infer<typeof backtestResultSchema>;
export type BacktestRunResponse = z.infer<typeof backtestRunResponseSchema>;
export type CreateBacktestRunInput = z.infer<typeof createBacktestRunSchema>;
export type WalkForwardConfig = z.infer<typeof walkForwardConfigSchema>;
export type WalkForwardResult = z.infer<typeof walkForwardResultSchema>;
