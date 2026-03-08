import { z } from 'zod';

import { uuidSchema } from './_shared.js';

export const membershipRoleSchema = z.enum(['owner', 'admin', 'member', 'viewer']);
export type MembershipRole = z.infer<typeof membershipRoleSchema>;

export const loginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});
export type LoginRequest = z.infer<typeof loginRequestSchema>;

export const authUserSchema = z.object({
  id: uuidSchema,
  email: z.string().email(),
  fullName: z.string(),
  tenantId: uuidSchema,
  role: membershipRoleSchema,
});
export type AuthUser = z.infer<typeof authUserSchema>;

export const loginResponseSchema = z.object({
  accessToken: z.string(),
  refreshToken: z.string(),
  user: authUserSchema,
});
export type LoginResponse = z.infer<typeof loginResponseSchema>;

export const refreshRequestSchema = z.object({ refreshToken: z.string() });
export type RefreshRequest = z.infer<typeof refreshRequestSchema>;

export const refreshResponseSchema = z.object({
  accessToken: z.string(),
  refreshToken: z.string(),
});
export type RefreshResponse = z.infer<typeof refreshResponseSchema>;

export const authMeResponseSchema = authUserSchema;
export type AuthMeResponse = z.infer<typeof authMeResponseSchema>;
