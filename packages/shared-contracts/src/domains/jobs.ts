import { z } from 'zod';

import { strategyTypeSchema, uuidSchema } from './_shared.js';

export const jobKindSchema = z.enum(['strategy_run', 'backtest_run']);

export const strategyRunQueuedEventSchema = z.object({
  jobId: uuidSchema,
  runId: uuidSchema,
  tenantId: uuidSchema,
  strategy: strategyTypeSchema,
  asOfDate: z.string().datetime().optional(),
});

export type JobKind = z.infer<typeof jobKindSchema>;
export type StrategyRunQueuedEvent = z.infer<typeof strategyRunQueuedEventSchema>;
