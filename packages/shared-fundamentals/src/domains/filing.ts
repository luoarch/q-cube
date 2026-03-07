import { z } from "zod";
import {
  batchStatusSchema,
  filingStatusSchema,
  filingTypeSchema,
  sourceProviderSchema
} from "./enums.js";

export const rawSourceBatchSchema = z.object({
  id: z.string().uuid(),
  source: sourceProviderSchema,
  year: z.number().int(),
  documentType: filingTypeSchema,
  status: batchStatusSchema,
  startedAt: z.string().datetime(),
  completedAt: z.string().datetime().nullable()
});

export const rawSourceFileSchema = z.object({
  id: z.string().uuid(),
  batchId: z.string().uuid(),
  filename: z.string(),
  url: z.string(),
  sha256Hash: z.string(),
  sizeBytes: z.number().int(),
  importedAt: z.string().datetime()
});

export const filingSchema = z.object({
  id: z.string().uuid(),
  issuerId: z.string().uuid(),
  source: sourceProviderSchema,
  filingType: filingTypeSchema,
  referenceDate: z.string(),
  versionNumber: z.number().int(),
  isRestatement: z.boolean(),
  supersedesFilingId: z.string().uuid().nullable(),
  status: filingStatusSchema,
  rawFileId: z.string().uuid().nullable(),
  validationResult: z.record(z.string(), z.unknown()).nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});

export type RawSourceBatch = z.infer<typeof rawSourceBatchSchema>;
export type RawSourceFile = z.infer<typeof rawSourceFileSchema>;
export type Filing = z.infer<typeof filingSchema>;
