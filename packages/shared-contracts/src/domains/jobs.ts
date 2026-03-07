import { z } from "zod";
import { strategyTypeSchema } from "./strategy.js";

export const runStatusSchema = z.enum(["pending", "running", "completed", "failed"]);

export const jobKindSchema = z.enum(["strategy_run", "backtest_run"]);

export const strategyRunQueuedEventSchema = z.object({
  jobId: z.string().uuid(),
  runId: z.string().uuid(),
  tenantId: z.string().uuid(),
  strategy: strategyTypeSchema,
  asOfDate: z.string().datetime().optional()
});

export type RunStatus = z.infer<typeof runStatusSchema>;
export type JobKind = z.infer<typeof jobKindSchema>;
export type StrategyRunQueuedEvent = z.infer<typeof strategyRunQueuedEventSchema>;
