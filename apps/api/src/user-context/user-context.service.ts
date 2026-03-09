import { randomUUID } from 'node:crypto';

import { Inject, Injectable, Logger } from '@nestjs/common';
import { type UserContextProfile, userContextProfileSchema } from '@q3/shared-contracts';
import { and, eq } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';
import { userContextProfiles } from '../db/schema.js';

import type { UpdateUserContext } from '@q3/shared-contracts';
import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

@Injectable()
export class UserContextService {
  private readonly logger = new Logger(UserContextService.name);

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
  ) {}

  async get(userId: string, tenantId: string): Promise<UserContextProfile | null> {
    const rows = await this.db
      .select()
      .from(userContextProfiles)
      .where(
        and(
          eq(userContextProfiles.userId, userId),
          eq(userContextProfiles.tenantId, tenantId),
        ),
      )
      .limit(1);

    const row = rows[0];
    if (!row) return null;

    return userContextProfileSchema.parse({
      ...row,
      createdAt: row.createdAt.toISOString(),
      updatedAt: row.updatedAt.toISOString(),
    });
  }

  async upsert(
    userId: string,
    tenantId: string,
    input: UpdateUserContext,
  ): Promise<UserContextProfile> {
    const existing = await this.get(userId, tenantId);

    if (existing) {
      const updateData: Record<string, unknown> = {
        updatedAt: new Date(),
      };
      if (input.preferredStrategy !== undefined) {
        updateData.preferredStrategy = input.preferredStrategy;
      }
      if (input.watchlistJson !== undefined) {
        updateData.watchlistJson = input.watchlistJson;
      }
      if (input.preferencesJson !== undefined) {
        updateData.preferencesJson = input.preferencesJson;
      }

      const rows = await this.db
        .update(userContextProfiles)
        .set(updateData)
        .where(
          and(
            eq(userContextProfiles.userId, userId),
            eq(userContextProfiles.tenantId, tenantId),
          ),
        )
        .returning();

      const row = rows[0]!;
      return userContextProfileSchema.parse({
        ...row,
        createdAt: row.createdAt.toISOString(),
        updatedAt: row.updatedAt.toISOString(),
      });
    }

    const rows = await this.db
      .insert(userContextProfiles)
      .values({
        id: randomUUID(),
        userId,
        tenantId,
        preferredStrategy: input.preferredStrategy ?? null,
        watchlistJson: input.watchlistJson ?? null,
        preferencesJson: input.preferencesJson ?? null,
      })
      .returning();

    const row = rows[0]!;
    return userContextProfileSchema.parse({
      ...row,
      createdAt: row.createdAt.toISOString(),
      updatedAt: row.updatedAt.toISOString(),
    });
  }
}
