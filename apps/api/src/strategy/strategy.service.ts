import {
  Inject,
  Injectable,
  InternalServerErrorException,
  Logger
} from "@nestjs/common";
import {
  type CreateStrategyRunInput,
  createStrategyRunResponseSchema,
  strategyRunResponseSchema,
  strategyRunQueuedEventSchema
} from "@q3/shared-contracts";
import { ConfigService } from "@nestjs/config";
import { and, desc, eq } from "drizzle-orm";
import type { NodePgDatabase } from "drizzle-orm/node-postgres";
import type { Redis } from "ioredis";
import { randomUUID } from "node:crypto";
import { DB } from "../database/database.constants.js";
import { REDIS } from "../redis/redis.constants.js";
import { jobs, strategyRuns } from "../db/schema.js";
import type * as schema from "../db/schema.js";
import type { EnvConfig } from "../config/env.schema.js";

@Injectable()
export class StrategyService {
  private readonly logger = new Logger(StrategyService.name);
  private readonly queueKey: string;

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
    @Inject(REDIS) private readonly redis: Redis,
    config: ConfigService<EnvConfig>
  ) {
    this.queueKey = config.get("STRATEGY_QUEUE_KEY", { infer: true })!;
  }

  async createRun(input: CreateStrategyRunInput) {
    const runId = randomUUID();
    const jobId = randomUUID();

    const [run] = await this.db.transaction(async (tx) => {
      const inserted = await tx
        .insert(strategyRuns)
        .values({
          id: runId,
          tenantId: input.tenantId,
          strategy: input.strategy,
          status: "pending",
          asOfDate: input.asOfDate ? new Date(input.asOfDate) : null
        })
        .returning();

      await tx.insert(jobs).values({
        id: jobId,
        tenantId: input.tenantId,
        kind: "strategy_run",
        status: "pending",
        payloadJson: {
          runId,
          strategy: input.strategy,
          asOfDate: input.asOfDate ?? null
        }
      });

      return inserted;
    });

    if (!run) {
      throw new InternalServerErrorException(
        "Failed to create strategy run"
      );
    }

    const queuedEvent = strategyRunQueuedEventSchema.parse({
      jobId,
      runId,
      tenantId: input.tenantId,
      strategy: input.strategy,
      asOfDate: input.asOfDate
    });

    if (this.redis.status !== "ready") {
      await this.redis.connect();
    }

    await this.redis.lpush(this.queueKey, JSON.stringify(queuedEvent));
    this.logger.log(`Queued strategy run ${runId} for tenant ${input.tenantId}`);

    return createStrategyRunResponseSchema.parse({
      run: {
        id: run.id,
        tenantId: run.tenantId,
        strategy: run.strategy,
        status: run.status,
        asOfDate: run.asOfDate ? run.asOfDate.toISOString() : null,
        errorMessage: run.errorMessage,
        result: run.resultJson,
        createdAt: run.createdAt.toISOString(),
        updatedAt: run.updatedAt.toISOString()
      },
      jobId
    });
  }

  async listRuns(tenantId: string) {
    const rows = await this.db
      .select()
      .from(strategyRuns)
      .where(eq(strategyRuns.tenantId, tenantId))
      .orderBy(desc(strategyRuns.createdAt));

    return rows.map((run) =>
      strategyRunResponseSchema.parse({
        id: run.id,
        tenantId: run.tenantId,
        strategy: run.strategy,
        status: run.status,
        asOfDate: run.asOfDate ? run.asOfDate.toISOString() : null,
        errorMessage: run.errorMessage,
        result: run.resultJson,
        createdAt: run.createdAt.toISOString(),
        updatedAt: run.updatedAt.toISOString(),
      })
    );
  }

  async getRun(id: string, tenantId: string) {
    const [run] = await this.db
      .select()
      .from(strategyRuns)
      .where(
        and(eq(strategyRuns.id, id), eq(strategyRuns.tenantId, tenantId))
      )
      .limit(1);

    if (!run) {
      return null;
    }

    return strategyRunResponseSchema.parse({
      id: run.id,
      tenantId: run.tenantId,
      strategy: run.strategy,
      status: run.status,
      asOfDate: run.asOfDate ? run.asOfDate.toISOString() : null,
      errorMessage: run.errorMessage,
      result: run.resultJson,
      createdAt: run.createdAt.toISOString(),
      updatedAt: run.updatedAt.toISOString()
    });
  }

  async setRunStatus(input: {
    runId: string;
    tenantId: string;
    jobId: string;
    status: "running" | "completed" | "failed";
    result?: unknown;
    errorMessage?: string;
  }) {
    await this.db.transaction(async (tx) => {
      await tx
        .update(strategyRuns)
        .set({
          status: input.status,
          resultJson: input.result ?? null,
          errorMessage: input.errorMessage ?? null,
          updatedAt: new Date()
        })
        .where(
          and(
            eq(strategyRuns.id, input.runId),
            eq(strategyRuns.tenantId, input.tenantId)
          )
        );

      await tx
        .update(jobs)
        .set({
          status: input.status,
          errorMessage: input.errorMessage ?? null,
          updatedAt: new Date()
        })
        .where(
          and(eq(jobs.id, input.jobId), eq(jobs.tenantId, input.tenantId))
        );
    });
  }
}
