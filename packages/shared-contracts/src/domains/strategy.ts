import { z } from "zod";
import { runStatusSchema, strategyTypeSchema, uuidSchema } from "./_shared.js";

export const createStrategyRunSchema = z.object({
  tenantId: uuidSchema,
  strategy: strategyTypeSchema,
  asOfDate: z.string().datetime().optional()
});

export const strategyResultSchema = z.object({
  rankedAssets: z.array(z.union([z.string(), z.object({ ticker: z.string() })])),
}).passthrough();

export type StrategyResult = z.infer<typeof strategyResultSchema>;

export const strategyRunResponseSchema = z.object({
  id: uuidSchema,
  tenantId: uuidSchema,
  strategy: strategyTypeSchema,
  status: runStatusSchema,
  asOfDate: z.string().datetime().nullable(),
  errorMessage: z.string().nullable(),
  result: strategyResultSchema.nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});

export const createStrategyRunResponseSchema = z.object({
  run: strategyRunResponseSchema,
  jobId: uuidSchema
});

export type CreateStrategyRunInput = z.infer<typeof createStrategyRunSchema>;
export type StrategyRunResponse = z.infer<typeof strategyRunResponseSchema>;
export type CreateStrategyRunResponse = z.infer<typeof createStrategyRunResponseSchema>;
