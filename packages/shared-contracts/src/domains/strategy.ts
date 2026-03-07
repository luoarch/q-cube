import { z } from "zod";
import { runStatusSchema } from "./jobs.js";

export const strategyTypeSchema = z.enum([
  "magic_formula_original",
  "magic_formula_brazil",
  "magic_formula_hybrid"
]);

export const createStrategyRunSchema = z.object({
  tenantId: z.string().uuid(),
  strategy: strategyTypeSchema,
  asOfDate: z.string().datetime().optional()
});

export const strategyRunResponseSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  strategy: strategyTypeSchema,
  status: runStatusSchema,
  asOfDate: z.string().datetime().nullable(),
  errorMessage: z.string().nullable(),
  result: z.unknown().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});

export const createStrategyRunResponseSchema = z.object({
  run: strategyRunResponseSchema,
  jobId: z.string().uuid()
});

export type StrategyType = z.infer<typeof strategyTypeSchema>;
export type CreateStrategyRunInput = z.infer<typeof createStrategyRunSchema>;
export type StrategyRunResponse = z.infer<typeof strategyRunResponseSchema>;
export type CreateStrategyRunResponse = z.infer<typeof createStrategyRunResponseSchema>;
