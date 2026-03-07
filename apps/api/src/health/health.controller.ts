import { Controller, Get, Inject } from "@nestjs/common";
import { SkipThrottle } from "@nestjs/throttler";
import {
  HealthCheck,
  HealthCheckService,
  HealthIndicator,
  type HealthIndicatorResult
} from "@nestjs/terminus";
import { sql } from "drizzle-orm";
import type { NodePgDatabase } from "drizzle-orm/node-postgres";
import type { Redis } from "ioredis";
import { DB } from "../database/database.constants.js";
import { REDIS } from "../redis/redis.constants.js";
import type * as schema from "../db/schema.js";

class DatabaseHealthIndicator extends HealthIndicator {
  constructor(private readonly db: NodePgDatabase<typeof schema>) {
    super();
  }

  async isHealthy(key: string): Promise<HealthIndicatorResult> {
    try {
      await this.db.execute(sql`SELECT 1`);
      return this.getStatus(key, true);
    } catch {
      return this.getStatus(key, false, { message: "Database unreachable" });
    }
  }
}

class RedisHealthIndicator extends HealthIndicator {
  constructor(private readonly redis: Redis) {
    super();
  }

  async isHealthy(key: string): Promise<HealthIndicatorResult> {
    try {
      if (this.redis.status !== "ready") {
        await this.redis.connect();
      }
      const pong = await this.redis.ping();
      return this.getStatus(key, pong === "PONG");
    } catch {
      return this.getStatus(key, false, { message: "Redis unreachable" });
    }
  }
}

@Controller("health")
@SkipThrottle()
export class HealthController {
  private readonly dbHealth: DatabaseHealthIndicator;
  private readonly redisHealth: RedisHealthIndicator;

  constructor(
    private readonly health: HealthCheckService,
    @Inject(DB) db: NodePgDatabase<typeof schema>,
    @Inject(REDIS) redis: Redis
  ) {
    this.dbHealth = new DatabaseHealthIndicator(db);
    this.redisHealth = new RedisHealthIndicator(redis);
  }

  @Get()
  @HealthCheck()
  check() {
    return this.health.check([
      () => this.dbHealth.isHealthy("database"),
      () => this.redisHealth.isHealthy("redis")
    ]);
  }
}
