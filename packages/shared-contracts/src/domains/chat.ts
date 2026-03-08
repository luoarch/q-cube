import { z } from 'zod';

import { uuidSchema } from './_shared.js';
import { agentIdSchema, councilModeSchema } from './council.js';

// --- Chat modes ---

export const chatModeSchema = z.enum([
  'free_chat',
  'agent_solo',
  'roundtable',
  'debate',
  'comparison',
]);
export type ChatMode = z.infer<typeof chatModeSchema>;

// --- Chat message roles ---

export const chatRoleSchema = z.enum([
  'user',
  'assistant',
  'system',
  'tool',
  'agent',
]);
export type ChatRole = z.infer<typeof chatRoleSchema>;

// --- Chat session ---

export const chatSessionSchema = z.object({
  id: uuidSchema,
  tenantId: uuidSchema,
  userId: uuidSchema,
  title: z.string().nullable(),
  mode: chatModeSchema,
  createdAt: z.string(),
  archivedAt: z.string().nullable(),
});
export type ChatSession = z.infer<typeof chatSessionSchema>;

export const createChatSessionSchema = z.object({
  mode: chatModeSchema.default('free_chat'),
  title: z.string().max(200).nullable().optional(),
});
export type CreateChatSession = z.infer<typeof createChatSessionSchema>;

// --- Chat message ---

export const chatMessageSchema = z.object({
  id: uuidSchema,
  sessionId: uuidSchema,
  role: chatRoleSchema,
  content: z.string(),
  agentId: agentIdSchema.nullable().optional(),
  toolCallsJson: z.unknown().nullable().optional(),
  tokensUsed: z.number().nullable().optional(),
  costUsd: z.number().nullable().optional(),
  providerUsed: z.string().nullable().optional(),
  modelUsed: z.string().nullable().optional(),
  fallbackLevel: z.number().nullable().optional(),
  createdAt: z.string(),
});
export type ChatMessage = z.infer<typeof chatMessageSchema>;

// --- Send message ---

export const sendMessageSchema = z.object({
  content: z.string().min(1).max(10_000),
  mode: chatModeSchema.optional(),
  agentIds: z.array(agentIdSchema).optional(),
  tickers: z.array(z.string()).optional(),
});
export type SendMessage = z.infer<typeof sendMessageSchema>;
