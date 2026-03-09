import { randomUUID } from 'node:crypto';

import { Inject, Injectable, Logger } from '@nestjs/common';
import {
  type BacktestRunResponse,
  type CreateBacktestRunInput,
  backtestRunResponseSchema,
} from '@q3/shared-contracts';
import { and, desc, eq } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';
import { backtestRuns } from '../db/schema.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

@Injectable()
export class BacktestService {
  private readonly logger = new Logger(BacktestService.name);

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
  ) {}

  async createRun(tenantId: string, input: CreateBacktestRunInput): Promise<BacktestRunResponse> {
    const id = randomUUID();

    const [run] = await this.db
      .insert(backtestRuns)
      .values({
        id,
        tenantId,
        status: 'pending',
        configJson: input.config,
      })
      .returning();

    this.logger.log(`Created backtest run ${id} for tenant ${tenantId}`);

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
