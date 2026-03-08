import { Inject, Injectable, Logger } from '@nestjs/common';
import {
  aiSuggestionSchema,
  aiSuggestionDetailSchema,
  type AISuggestion,
  type AISuggestionDetail,
  type AISuggestionsQuery,
  type UpdateReviewStatus,
} from '@q3/shared-contracts';
import { and, desc, eq, ne, sql } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';
import { aiExplanations, aiResearchNotes, aiSuggestions } from '../db/schema.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

@Injectable()
export class AIService {
  private readonly logger = new Logger(AIService.name);

  constructor(@Inject(DB) private readonly db: NodePgDatabase<typeof schema>) {}

  async listSuggestions(tenantId: string, query: AISuggestionsQuery): Promise<AISuggestion[]> {
    const conditions = [eq(aiSuggestions.tenantId, tenantId)];

    if (query.module) {
      conditions.push(eq(aiSuggestions.module, query.module));
    }
    if (query.reviewStatus) {
      conditions.push(eq(aiSuggestions.reviewStatus, query.reviewStatus));
    }
    if (query.triggerEntityId) {
      conditions.push(eq(aiSuggestions.triggerEntityId, query.triggerEntityId));
    }
    if (!query.includeArchived) {
      conditions.push(ne(aiSuggestions.reviewStatus, 'expired'));
    }

    const rows = await this.db
      .select()
      .from(aiSuggestions)
      .where(and(...conditions))
      .orderBy(desc(aiSuggestions.createdAt));

    return rows.map((row) => this.mapSuggestion(row));
  }

  async getSuggestionDetail(id: string, tenantId: string): Promise<AISuggestionDetail | null> {
    const [row] = await this.db
      .select()
      .from(aiSuggestions)
      .where(and(eq(aiSuggestions.id, id), eq(aiSuggestions.tenantId, tenantId)))
      .limit(1);

    if (!row) return null;

    const explanationRows = await this.db
      .select()
      .from(aiExplanations)
      .where(eq(aiExplanations.suggestionId, id));

    const noteRows = await this.db
      .select()
      .from(aiResearchNotes)
      .where(eq(aiResearchNotes.suggestionId, id));

    return aiSuggestionDetailSchema.parse({
      ...this.mapSuggestion(row),
      explanations: explanationRows.map((e) => ({
        id: e.id,
        suggestionId: e.suggestionId,
        entityType: e.entityType,
        entityId: e.entityId,
        explanationType: e.explanationType,
        content: e.content,
        createdAt: e.createdAt.toISOString(),
      })),
      researchNotes: noteRows.map((n) => ({
        id: n.id,
        suggestionId: n.suggestionId,
        noteType: n.noteType,
        content: n.content,
        createdAt: n.createdAt.toISOString(),
      })),
    });
  }

  async getSuggestionsByEntity(entityId: string, tenantId: string): Promise<AISuggestion[]> {
    const rows = await this.db
      .select()
      .from(aiSuggestions)
      .where(and(eq(aiSuggestions.triggerEntityId, entityId), eq(aiSuggestions.tenantId, tenantId)))
      .orderBy(desc(aiSuggestions.createdAt));

    return rows.map((row) => this.mapSuggestion(row));
  }

  async updateReviewStatus(
    id: string,
    tenantId: string,
    userId: string,
    input: UpdateReviewStatus,
  ): Promise<AISuggestion | null> {
    const [updated] = await this.db
      .update(aiSuggestions)
      .set({
        reviewStatus: input.reviewStatus,
        reviewedBy: userId,
        reviewedAt: new Date(),
      })
      .where(and(eq(aiSuggestions.id, id), eq(aiSuggestions.tenantId, tenantId)))
      .returning();

    if (!updated) return null;
    return this.mapSuggestion(updated);
  }

  private mapSuggestion(row: typeof aiSuggestions.$inferSelect): AISuggestion {
    return aiSuggestionSchema.parse({
      id: row.id,
      tenantId: row.tenantId,
      module: row.module,
      triggerEvent: row.triggerEvent,
      triggerEntityId: row.triggerEntityId,
      inputHash: row.inputHash,
      promptVersion: row.promptVersion,
      outputSchemaVersion: row.outputSchemaVersion,
      outputText: row.outputText,
      structuredOutput: row.structuredOutput as Record<string, unknown> | null,
      confidence: row.confidence,
      modelUsed: row.modelUsed,
      modelVersion: row.modelVersion,
      tokensUsed: Number(row.tokensUsed),
      promptTokens: Number(row.promptTokens),
      completionTokens: Number(row.completionTokens),
      costUsd: Number(row.costUsd),
      reviewStatus: row.reviewStatus,
      reviewedBy: row.reviewedBy ?? null,
      reviewedAt: row.reviewedAt ? row.reviewedAt.toISOString() : null,
      createdAt: row.createdAt.toISOString(),
    });
  }
}
