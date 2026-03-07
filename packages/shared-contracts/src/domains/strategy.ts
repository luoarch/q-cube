import { z } from "zod";
import { runStatusSchema, strategyTypeSchema, uuidSchema } from "./_shared.js";

export { strategyTypeSchema };

export const createStrategyRunSchema = z.object({
  tenantId: uuidSchema,
  strategy: strategyTypeSchema,
  asOfDate: z.string().datetime().optional()
});

export const strategyRunResponseSchema = z.object({
  id: uuidSchema,
  tenantId: uuidSchema,
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
  jobId: uuidSchema
});

export type { StrategyType } from "./_shared.js";
export type CreateStrategyRunInput = z.infer<typeof createStrategyRunSchema>;
export type StrategyRunResponse = z.infer<typeof strategyRunResponseSchema>;
export type CreateStrategyRunResponse = z.infer<typeof createStrategyRunResponseSchema>;
