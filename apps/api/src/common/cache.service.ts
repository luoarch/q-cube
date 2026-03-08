import { Inject, Injectable } from '@nestjs/common';

import { REDIS } from '../redis/redis.constants.js';

import type { Redis } from 'ioredis';
import type { z } from 'zod';

@Injectable()
export class CacheService {
  constructor(@Inject(REDIS) private readonly redis: Redis) {}

  async get<T>(key: string): Promise<T | null> {
    try {
      const raw = await this.redis.get(key);
      if (!raw) return null;
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }

  async getValidated<T>(key: string, schema: z.ZodType<T>): Promise<T | null> {
    try {
      const raw = await this.redis.get(key);
      if (!raw) return null;
      return schema.parse(JSON.parse(raw));
    } catch {
      return null;
    }
  }

  async set(key: string, value: unknown, ttlSeconds: number): Promise<void> {
    await this.redis.set(key, JSON.stringify(value), 'EX', ttlSeconds);
  }

  async del(pattern: string): Promise<void> {
    const keys = await this.redis.keys(pattern);
    if (keys.length > 0) {
      await this.redis.del(...keys);
    }
  }
}
