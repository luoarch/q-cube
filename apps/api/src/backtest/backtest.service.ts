import { randomUUID } from 'node:crypto';

import { Inject, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  type BacktestRunResponse,
  type CreateBacktestRunInput,
  backtestRunQueuedEventSchema,
  backtestRunResponseSchema,
} from '@q3/shared-contracts';
import { and, desc, eq } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';
import { backtestRuns, jobs } from '../db/schema.js';
import { REDIS } from '../redis/redis.constants.js';

import type { EnvConfig } from '../config/env.schema.js';
import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';
import type { Redis } from 'ioredis';

@Injectable()
export class BacktestService {
  private readonly logger = new Logger(BacktestService.name);
  private readonly queueKey: string;

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
    @Inject(REDIS) private readonly redis: Redis,
    config: ConfigService<EnvConfig>,
  ) {
    this.queueKey = config.get('BACKTEST_QUEUE_KEY', { infer: true })!;
  }

  async createRun(tenantId: string, input: CreateBacktestRunInput): Promise<BacktestRunResponse> {
    const runId = randomUUID();
    const jobId = randomUUID();

    const [run] = await this.db.transaction(async (tx) => {
      const inserted = await tx
        .insert(backtestRuns)
        .values({
          id: runId,
          tenantId,
          status: 'pending',
          configJson: input.config,
        })
        .returning();

      await tx.insert(jobs).values({
        id: jobId,
        tenantId,
        kind: 'backtest_run',
        status: 'pending',
        payloadJson: {
          runId,
          config: input.config,
        },
      });

      return inserted;
    });

    // Push to Redis queue for Celery worker
    const queuedEvent = backtestRunQueuedEventSchema.parse({
      jobId,
      runId,
      tenantId,
      config: input.config,
    });

    if (this.redis.status !== 'ready') {
      await this.redis.connect();
    }

    await this.redis.lpush(this.queueKey, JSON.stringify(queuedEvent));
    this.logger.log(`Queued backtest run ${runId} for tenant ${tenantId}`);

    return this._serialize(run!);
  }

  async listRuns(tenantId: string): Promise<BacktestRunResponse[]> {
    const rows = await this.db
      .select()
      .from(backtestRuns)
      .where(eq(backtestRuns.tenantId, tenantId))
      .orderBy(desc(backtestRuns.createdAt))
      .limit(50);

    return rows.map((r) => this._serialize(r));
  }

  async getRun(id: string, tenantId: string): Promise<BacktestRunResponse | null> {
    const [run] = await this.db
      .select()
      .from(backtestRuns)
      .where(and(eq(backtestRuns.id, id), eq(backtestRuns.tenantId, tenantId)))
      .limit(1);

    return run ? this._serialize(run) : null;
  }

  private _serialize(run: typeof backtestRuns.$inferSelect): BacktestRunResponse {
    return backtestRunResponseSchema.parse({
      id: run.id,
      tenantId: run.tenantId,
      status: run.status,
      config: run.configJson,
      result: run.metricsJson,
      errorMessage: run.errorMessage,
      createdAt: run.createdAt.toISOString(),
      updatedAt: run.updatedAt.toISOString(),
    });
  }
}
