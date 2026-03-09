import { Controller, Get, Inject } from '@nestjs/common';
import {
  HealthCheck,
  HealthCheckService,
  HealthIndicator,
} from '@nestjs/terminus';

import type { HealthIndicatorResult } from '@nestjs/terminus';
import { SkipThrottle } from '@nestjs/throttler';
import { sql } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';
import { REDIS } from '../redis/redis.constants.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';
import type { Redis } from 'ioredis';

class DatabaseHealthIndicator extends HealthIndicator {
  constructor(private readonly db: NodePgDatabase<typeof schema>) {
    super();
  }

  async isHealthy(key: string): Promise<HealthIndicatorResult> {
    try {
      await this.db.execute(sql`SELECT 1`);
      return this.getStatus(key, true);
    } catch {
      return this.getStatus(key, false, { message: 'Database unreachable' });
    }
  }
}

class RedisHealthIndicator extends HealthIndicator {
  constructor(private readonly redis: Redis) {
    super();
  }

  async isHealthy(key: string): Promise<HealthIndicatorResult> {
    try {
      if (this.redis.status !== 'ready') {
        await this.redis.connect();
      }
      const pong = await this.redis.ping();
      return this.getStatus(key, pong === 'PONG');
    } catch {
      return this.getStatus(key, false, { message: 'Redis unreachable' });
    }
  }
}

class ServiceHealthIndicator extends HealthIndicator {
  constructor(
    private readonly url: string,
    private readonly timeoutMs = 5000,
  ) {
    super();
  }

  async isHealthy(key: string): Promise<HealthIndicatorResult> {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);
      const res = await fetch(this.url, { signal: controller.signal });
      clearTimeout(timer);
      return this.getStatus(key, res.ok);
    } catch {
      return this.getStatus(key, false, { message: `${key} unreachable` });
    }
  }
}

@Controller('health')
@SkipThrottle()
export class HealthController {
  private readonly dbHealth: DatabaseHealthIndicator;
  private readonly redisHealth: RedisHealthIndicator;
  private readonly quantEngine: ServiceHealthIndicator;
  private readonly marketIngestion: ServiceHealthIndicator;
  private readonly fundamentalsEngine: ServiceHealthIndicator;

  constructor(
    private readonly health: HealthCheckService,
    @Inject(DB) db: NodePgDatabase<typeof schema>,
    @Inject(REDIS) redis: Redis,
  ) {
    this.dbHealth = new DatabaseHealthIndicator(db);
    this.redisHealth = new RedisHealthIndicator(redis);
    this.quantEngine = new ServiceHealthIndicator('http://localhost:8100/health');
    this.marketIngestion = new ServiceHealthIndicator('http://localhost:8200/health');
    this.fundamentalsEngine = new ServiceHealthIndicator('http://localhost:8300/health');
  }

  @Get()
  @HealthCheck()
  check() {
    return this.health.check([
      () => this.dbHealth.isHealthy('database'),
      () => this.redisHealth.isHealthy('redis'),
      () => this.quantEngine.isHealthy('quant-engine'),
      () => this.marketIngestion.isHealthy('market-ingestion'),
      () => this.fundamentalsEngine.isHealthy('fundamentals-engine'),
    ]);
  }
}
