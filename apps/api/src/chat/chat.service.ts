import { randomUUID } from 'node:crypto';

import { Inject, Injectable, Logger } from '@nestjs/common';
import {
  type ChatMessage,
  type ChatSession,
  type CreateChatSession,
  chatMessageSchema,
  chatSessionSchema,
} from '@q3/shared-contracts';
import { and, desc, eq } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';
import { chatMessages, chatSessions } from '../db/schema.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
  ) {}

  async createSession(tenantId: string, userId: string, input: CreateChatSession) {
    const id = randomUUID();
    const rows = await this.db
      .insert(chatSessions)
      .values({
        id,
        tenantId,
        userId,
        title: input.title ?? null,
        mode: input.mode ?? 'free_chat',
      })
      .returning();

    const row = rows[0]!;
    return chatSessionSchema.parse({
      ...row,
      createdAt: row.createdAt.toISOString(),
      archivedAt: row.archivedAt?.toISOString() ?? null,
    });
  }

  async listSessions(tenantId: string, userId: string) {
    const rows = await this.db
      .select()
      .from(chatSessions)
      .where(and(eq(chatSessions.tenantId, tenantId), eq(chatSessions.userId, userId)))
      .orderBy(desc(chatSessions.createdAt))
      .limit(50);

    return rows.map((row) =>
      chatSessionSchema.parse({
        ...row,
        createdAt: row.createdAt.toISOString(),
        archivedAt: row.archivedAt?.toISOString() ?? null,
      }),
    );
  }

  async getMessages(sessionId: string, tenantId: string) {
    const rows = await this.db
      .select()
      .from(chatMessages)
      .where(eq(chatMessages.sessionId, sessionId))
      .orderBy(chatMessages.createdAt);

    return rows.map((row) =>
      chatMessageSchema.parse({
        ...row,
        costUsd: row.costUsd != null ? Number(row.costUsd) : null,
        createdAt: row.createdAt.toISOString(),
      }),
    );
  }

  async addMessage(
    sessionId: string,
    role: 'user' | 'assistant' | 'system' | 'tool' | 'agent',
    content: string,
    extra?: {
      agentId?: string;
      toolCallsJson?: unknown;
      tokensUsed?: number;
      costUsd?: number;
      providerUsed?: string;
      modelUsed?: string;
      fallbackLevel?: number;
    },
  ) {
    const id = randomUUID();
    const rows = await this.db
      .insert(chatMessages)
      .values({
        id,
        sessionId,
        role,
        content,
        agentId: extra?.agentId ?? null,
        toolCallsJson: extra?.toolCallsJson ?? null,
        tokensUsed: extra?.tokensUsed ?? null,
        costUsd: extra?.costUsd?.toString() ?? null,
        providerUsed: extra?.providerUsed ?? null,
        modelUsed: extra?.modelUsed ?? null,
        fallbackLevel: extra?.fallbackLevel ?? null,
      })
      .returning();

    const row = rows[0]!;
    return chatMessageSchema.parse({
      ...row,
      costUsd: row.costUsd != null ? Number(row.costUsd) : null,
      createdAt: row.createdAt.toISOString(),
    });
  }
}
