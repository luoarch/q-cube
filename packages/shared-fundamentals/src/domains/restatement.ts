import { z } from "zod";

export const restatementEventSchema = z.object({
  id: z.string().uuid(),
  originalFilingId: z.string().uuid(),
  newFilingId: z.string().uuid(),
  detectedAt: z.string().datetime(),
  affectedMetrics: z.record(z.string(), z.unknown())
});

export type RestatementEvent = z.infer<typeof restatementEventSchema>;
