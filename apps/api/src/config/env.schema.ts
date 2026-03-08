import { z } from 'zod';

export const envSchema = z.object({
  PORT: z.coerce.number().default(4000),
  DATABASE_URL: z.string().default('postgresql://127.0.0.1:5432/q3'),
  REDIS_URL: z.string().default('redis://127.0.0.1:6379'),
  STRATEGY_QUEUE_KEY: z.string().default('q3:strategy:jobs'),
  JWT_SECRET: z.string().min(32),
  JWT_EXPIRY: z.string().default('30m'),
  JWT_REFRESH_EXPIRY: z.string().default('7d'),
  LOGIN_MAX_ATTEMPTS: z.coerce.number().default(5),
  LOGIN_LOCKOUT_MINUTES: z.coerce.number().default(15),
});

export type EnvConfig = z.infer<typeof envSchema>;

export function validateEnv(config: Record<string, unknown>): EnvConfig {
  return envSchema.parse(config);
}
