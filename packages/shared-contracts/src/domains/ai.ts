import { z } from "zod";
import { uuidSchema } from "./_shared.js";

// ---------------------------------------------------------------------------
// Enums (SSOT — mirrored from Python AIModule, ReviewStatus, etc.)
// ---------------------------------------------------------------------------

export const aiModuleSchema = z.enum(["ranking_explainer", "backtest_narrator"]);
export type AIModule = z.infer<typeof aiModuleSchema>;

export const reviewStatusSchema = z.enum(["pending", "approved", "rejected", "expired"]);
export type ReviewStatus = z.infer<typeof reviewStatusSchema>;

export const confidenceLevelSchema = z.enum(["high", "medium", "low"]);
export type ConfidenceLevel = z.infer<typeof confidenceLevelSchema>;

export const explanationTypeSchema = z.enum(["position", "sector", "outlier", "metric"]);
export type ExplanationType = z.infer<typeof explanationTypeSchema>;

export const noteTypeSchema = z.enum(["summary", "concern", "highlight", "recommendation"]);
export type NoteType = z.infer<typeof noteTypeSchema>;

// ---------------------------------------------------------------------------
// AI Suggestion
// ---------------------------------------------------------------------------

export const aiSuggestionSchema = z.object({
  id: uuidSchema,
  tenantId: uuidSchema,
  module: aiModuleSchema,
  triggerEvent: z.string(),
  triggerEntityId: uuidSchema,
  inputHash: z.string(),
  promptVersion: z.string(),
  outputSchemaVersion: z.string(),
  outputText: z.string(),
  structuredOutput: z.record(z.string(), z.unknown()).nullable(),
  confidence: confidenceLevelSchema,
  modelUsed: z.string(),
  modelVersion: z.string(),
  tokensUsed: z.number().int(),
  promptTokens: z.number().int(),
  completionTokens: z.number().int(),
  costUsd: z.number(),
  reviewStatus: reviewStatusSchema,
  reviewedBy: uuidSchema.nullable(),
  reviewedAt: z.string().datetime().nullable(),
  createdAt: z.string().datetime(),
});
export type AISuggestion = z.infer<typeof aiSuggestionSchema>;

// ---------------------------------------------------------------------------
// AI Explanation
// ---------------------------------------------------------------------------

export const aiExplanationSchema = z.object({
  id: uuidSchema,
  suggestionId: uuidSchema,
  entityType: z.string(),
  entityId: z.string(),
  explanationType: explanationTypeSchema,
  content: z.string(),
  createdAt: z.string().datetime(),
});
export type AIExplanation = z.infer<typeof aiExplanationSchema>;

// ---------------------------------------------------------------------------
// AI Research Note
// ---------------------------------------------------------------------------

export const aiResearchNoteSchema = z.object({
  id: uuidSchema,
  suggestionId: uuidSchema,
  noteType: noteTypeSchema,
  content: z.string(),
  createdAt: z.string().datetime(),
});
export type AIResearchNote = z.infer<typeof aiResearchNoteSchema>;

// ---------------------------------------------------------------------------
// Detail (nested response)
// ---------------------------------------------------------------------------

export const aiSuggestionDetailSchema = aiSuggestionSchema.extend({
  explanations: z.array(aiExplanationSchema),
  researchNotes: z.array(aiResearchNoteSchema),
});
export type AISuggestionDetail = z.infer<typeof aiSuggestionDetailSchema>;

// ---------------------------------------------------------------------------
// Update review status
// ---------------------------------------------------------------------------

export const updateReviewStatusSchema = z.object({
  reviewStatus: z.enum(["approved", "rejected"]),
});
export type UpdateReviewStatus = z.infer<typeof updateReviewStatusSchema>;

// ---------------------------------------------------------------------------
// List query params
// ---------------------------------------------------------------------------

export const aiSuggestionsQuerySchema = z.object({
  module: aiModuleSchema.optional(),
  reviewStatus: reviewStatusSchema.optional(),
  triggerEntityId: uuidSchema.optional(),
  includeArchived: z.coerce.boolean().optional().default(false),
});
export type AISuggestionsQuery = z.infer<typeof aiSuggestionsQuerySchema>;
