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
// --- Statistical metrics (PSR / DSR) ---

export const statisticalMetricsSchema = z.object({
  psr: z.number(),
  dsr: z.number(),
  skewness: z.number(),
  excessKurtosis: z.number(),
  nReturns: z.number().int(),
  nTrials: z.number().int(),
});

// --- OOS Report ---

export const oosReportSchema = z.object({
  isMetrics: backtestMetricsSchema,
  oosMetrics: backtestMetricsSchema,
  isStatistical: statisticalMetricsSchema,
  oosStatistical: statisticalMetricsSchema,
  degradation: z.record(z.string(), z.number()),
  isPeriod: z.object({ start: z.string(), end: z.string() }),
  oosPeriod: z.object({ start: z.string(), end: z.string() }),
  fragile: z.boolean(),
});

// --- Subperiod Report ---

export const subperiodEntrySchema = z.object({
  label: z.string(),
  start: z.string(),
  end: z.string(),
  metrics: backtestMetricsSchema,
  returnsStats: z.object({ mean: z.number(), count: z.number().int() }),
});

export const regimeSummarySchema = z.record(
  z.string(),
  z.object({
    count: z.number().int(),
    avgSharpe: z.number(),
    avgCagr: z.number(),
    avgMaxDd: z.number(),
  })
);

export const subperiodReportSchema = z.object({
  subperiods: z.array(subperiodEntrySchema),
  rollingSharpe: z.array(z.object({ endDate: z.string(), sharpe: z.number() })),
  regimeSummary: regimeSummarySchema,
  fragile: z.boolean(),
});

// --- Sensitivity Report ---

export const sensitivityVariationSchema = z.object({
  param: z.string(),
  value: z.union([z.string(), z.number()]),
  metrics: backtestMetricsSchema,
  deltaSharpe: z.number(),
  deltaCagr: z.number(),
});

export const sensitivityReportSchema = z.object({
  baseMetrics: backtestMetricsSchema,
  variations: z.array(sensitivityVariationSchema),
  robust: z.boolean(),
});

// --- Research Manifest ---

export const researchManifestSchema = z.object({
  strategy: z.string(),
  variant: z.string(),
  experimentId: z.string(),
  startDate: z.string(),
  endDate: z.string(),
  split: z.string(),
  universeRules: z.record(z.string(), z.unknown()),
  costModel: costModelSchema.partial(),
  parameters: z.record(z.string(), z.unknown()),
  commitHash: z.string(),
  formulaVersion: z.number().int(),
  createdAt: z.string(),
  nTrials: z.number().int(),
  metricsSummary: z.record(z.string(), z.number()).optional(),
  statisticalMetrics: statisticalMetricsSchema.partial().optional(),
});

export type WalkForwardConfig = z.infer<typeof walkForwardConfigSchema>;
export type WalkForwardResult = z.infer<typeof walkForwardResultSchema>;
export type StatisticalMetrics = z.infer<typeof statisticalMetricsSchema>;
export type OOSReport = z.infer<typeof oosReportSchema>;
export type SubperiodReport = z.infer<typeof subperiodReportSchema>;
export type SensitivityReport = z.infer<typeof sensitivityReportSchema>;
export type ResearchManifest = z.infer<typeof researchManifestSchema>;
