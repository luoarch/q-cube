import { z } from 'zod';

import { uuidSchema } from './_shared.js';

export const userContextProfileSchema = z.object({
  id: uuidSchema,
  userId: uuidSchema,
  tenantId: uuidSchema,
  preferredStrategy: z.string().nullable(),
  watchlistJson: z.array(z.string()).nullable(),
  preferencesJson: z
    .object({
      defaultChatMode: z.string().optional(),
      favoriteAgents: z.array(z.string()).optional(),
      language: z.string().optional(),
    })
    .nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type UserContextProfile = z.infer<typeof userContextProfileSchema>;

export const updateUserContextSchema = z.object({
  preferredStrategy: z.string().max(50).nullable().optional(),
  watchlistJson: z.array(z.string().max(12)).max(50).nullable().optional(),
  preferencesJson: z
    .object({
      defaultChatMode: z.string().optional(),
      favoriteAgents: z.array(z.string()).optional(),
      language: z.string().optional(),
    })
    .nullable()
    .optional(),
});

export type UpdateUserContext = z.infer<typeof updateUserContextSchema>;
