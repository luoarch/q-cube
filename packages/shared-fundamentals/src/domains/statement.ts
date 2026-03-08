import { z } from 'zod';

import { periodTypeSchema, scopeTypeSchema, statementTypeSchema } from './enums.js';

export const statementLineSchema = z.object({
  id: z.string().uuid(),
  filingId: z.string().uuid(),
  statementType: statementTypeSchema,
  scope: scopeTypeSchema,
  periodType: periodTypeSchema,
  referenceDate: z.string(),
  canonicalKey: z.string().nullable(),
  asReportedLabel: z.string(),
  asReportedCode: z.string(),
  normalizedValue: z.number().nullable(),
  currency: z.string(),
  unitScale: z.string(),
});

export type StatementLine = z.infer<typeof statementLineSchema>;
