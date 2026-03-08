import { z } from 'zod';

import { metricCodeSchema, periodTypeSchema } from './enums.js';

export const computedMetricSchema = z.object({
  id: z.string().uuid(),
  issuerId: z.string().uuid(),
  securityId: z.string().uuid().nullable(),
  metricCode: metricCodeSchema,
  periodType: periodTypeSchema,
  referenceDate: z.string(),
  value: z.number().nullable(),
  formulaVersion: z.number().int(),
  inputsSnapshotJson: z.record(z.string(), z.unknown()),
  sourceFilingIdsJson: z.array(z.string().uuid()),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export type ComputedMetric = z.infer<typeof computedMetricSchema>;
