import { z } from 'zod';

// --- Source precedence ---

export const sourceTypeSchema = z.enum([
  'structured_internal',
  'internal_rag',
  'external_web',
  'model_prior',
]);
export type SourceType = z.infer<typeof sourceTypeSchema>;

export const SOURCE_PRECEDENCE: Record<SourceType, number> = {
  structured_internal: 1,
  internal_rag: 2,
  external_web: 3,
  model_prior: 4,
};

// --- Citation ---

export const citationSchema = z.object({
  sourceType: sourceTypeSchema,
  entityType: z.string(),
  entityId: z.string(),
  snippet: z.string(),
  label: z.string().optional(),
});
export type Citation = z.infer<typeof citationSchema>;

// --- Response with citations ---

export const citedResponseSchema = z.object({
  content: z.string(),
  citations: z.array(citationSchema),
  divergences: z.array(z.string()),
});
export type CitedResponse = z.infer<typeof citedResponseSchema>;
