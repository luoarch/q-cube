import { Injectable } from "@nestjs/common";
import {
  type CreateStrategyRunInput,
  createStrategyRunResponseSchema,
  strategyRunResponseSchema,
  strategyRunQueuedEventSchema
} from "@q3/shared-contracts";
import { and, eq } from "drizzle-orm";
import { randomUUID } from "node:crypto";
import { db, redis, STRATEGY_QUEUE_KEY } from "./infrastructure.js";
import { jobs, strategyRuns } from "./db/schema.js";

@Injectable()
export class StrategyService {
  async createRun(input: CreateStrategyRunInput) {
    const runId = randomUUID();
    const jobId = randomUUID();

    await db.transaction(async (tx) => {
      await tx.insert(strategyRuns).values({
        id: runId,
        tenantId: input.tenantId,
        strategy: input.strategy,
        status: "pending",
        asOfDate: input.asOfDate ? new Date(input.asOfDate) : null
      });

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
    });

    const [run] = await db
      .select()
      .from(strategyRuns)
      .where(eq(strategyRuns.id, runId))
      .limit(1);

    if (!run) {
      throw new Error("failed to load strategy run after creation");
    }

    const queuedEvent = strategyRunQueuedEventSchema.parse({
      jobId,
      runId,
      tenantId: input.tenantId,
      strategy: input.strategy,
      asOfDate: input.asOfDate
    });

    if (redis.status !== "ready") {
      await redis.connect();
    }

    await redis.lpush(STRATEGY_QUEUE_KEY, JSON.stringify(queuedEvent));

    const response = createStrategyRunResponseSchema.parse({
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

    return response;
  }

  async getRun(id: string) {
    const [run] = await db
      .select()
      .from(strategyRuns)
      .where(eq(strategyRuns.id, id))
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
    await db.transaction(async (tx) => {
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
        .where(and(eq(jobs.id, input.jobId), eq(jobs.tenantId, input.tenantId)));
    });
  }
}
