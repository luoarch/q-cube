import { randomUUID } from 'node:crypto';

import { Inject, Injectable, Logger } from '@nestjs/common';
import { eq } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';
import {
  councilDebates,
  councilOpinions,
  councilSessions,
  councilSyntheses,
} from '../db/schema.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

/** Helper: read snake_case or camelCase from a mixed-casing object. */
function sc<T>(obj: Record<string, unknown>, camel: string, snake: string): T | undefined {
  return (obj[camel] ?? obj[snake]) as T | undefined;
}

@Injectable()
export class CouncilService {
  private readonly logger = new Logger(CouncilService.name);

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
  ) {}

  /**
   * Persist a full council result to dedicated tables.
   * Returns the council_session ID.
   */
  async persistCouncilResult(
    chatSessionId: string,
    tenantId: string,
    mode: string,
    tickers: string[],
    agentIds: string[],
    councilResult: Record<string, unknown>,
  ): Promise<string> {
    const councilSessionId = randomUUID();

    try {
      // 1. council_sessions
      await this.db.insert(councilSessions).values({
        id: councilSessionId,
        chatSessionId,
        tenantId,
        mode: mode as 'solo' | 'roundtable' | 'debate' | 'comparison',
        assetIds: tickers,
        agentIds,
        status: 'completed',
      });

      // 2. council_opinions
      const opinions = (councilResult.opinions ?? []) as Array<Record<string, unknown>>;
      for (const op of opinions) {
        const agentId = sc<string>(op, 'agentId', 'agent_id') ?? 'unknown';
        const verdict = sc<string>(op, 'verdict', 'verdict') ?? 'insufficient_data';
        const confidence = sc<number>(op, 'confidence', 'confidence') ?? 0;
        const profileVersion = sc<number>(op, 'profileVersion', 'profile_version') ?? 1;
        const promptVersion = sc<number>(op, 'promptVersion', 'prompt_version') ?? 1;
        const providerUsed = sc<string>(op, 'providerUsed', 'provider_used');
        const modelUsed = sc<string>(op, 'modelUsed', 'model_used');
        const fallbackLevel = sc<number>(op, 'fallbackLevel', 'fallback_level');
        const tokensUsed = sc<number>(op, 'tokensUsed', 'tokens_used');
        const costUsd = sc<number>(op, 'costUsd', 'cost_usd');
        const hardRejects = sc<string[]>(op, 'hardRejectsTriggered', 'hard_rejects_triggered') ?? [];

        await this.db.insert(councilOpinions).values({
          id: randomUUID(),
          councilSessionId,
          agentId,
          verdict: verdict as 'buy' | 'watch' | 'avoid' | 'insufficient_data',
          confidence,
          opinionJson: op,
          hardRejectsJson: hardRejects.length > 0 ? hardRejects : null,
          profileVersion,
          promptVersion,
          providerUsed: providerUsed ?? null,
          modelUsed: modelUsed ?? null,
          fallbackLevel: fallbackLevel ?? null,
          tokensUsed: tokensUsed ?? null,
          costUsd: costUsd?.toString() ?? null,
        });
      }

      // 3. council_debates (if debate mode)
      const debateLog = sc<Array<Record<string, unknown>>>(
        councilResult, 'debateLog', 'debate_log',
      ) ?? [];
      for (const round of debateLog) {
        const roundNumber = sc<number>(round, 'roundNumber', 'round_number') ?? 0;
        const agentId = sc<string>(round, 'agentId', 'agent_id') ?? 'unknown';
        const content = sc<string>(round, 'content', 'content') ?? '';
        const targetAgentId = sc<string>(round, 'targetAgentId', 'target_agent_id');
        const providerUsed = sc<string>(round, 'providerUsed', 'provider_used');
        const modelUsed = sc<string>(round, 'modelUsed', 'model_used');

        await this.db.insert(councilDebates).values({
          id: randomUUID(),
          councilSessionId,
          roundNumber,
          agentId,
          content,
          targetAgentId: targetAgentId ?? null,
          providerUsed: providerUsed ?? null,
          modelUsed: modelUsed ?? null,
        });
      }

      // 4. council_syntheses
      const synthesis = sc<Record<string, unknown>>(
        councilResult, 'moderatorSynthesis', 'moderator_synthesis',
      );
      const scoreboard = sc<Record<string, unknown>>(
        councilResult, 'scoreboard', 'scoreboard',
      );
      const conflictMatrix = sc<unknown[]>(
        councilResult, 'conflictMatrix', 'conflict_matrix',
      );

      if (synthesis) {
        const overallAssessment = sc<string>(
          synthesis, 'overallAssessment', 'overall_assessment',
        ) ?? '';

        await this.db.insert(councilSyntheses).values({
          id: randomUUID(),
          councilSessionId,
          scoreboardJson: scoreboard ?? {},
          conflictsJson: conflictMatrix ?? [],
          synthesisText: overallAssessment,
        });
      }

      this.logger.log(
        `Persisted council session ${councilSessionId} (${mode}, ${opinions.length} opinions, ${debateLog.length} debate rounds)`,
      );

      return councilSessionId;
    } catch (err) {
      this.logger.error(`Failed to persist council result: ${err}`);
      throw err;
    }
  }

  /**
   * Get council session by chat session ID.
   */
  async getByChat(chatSessionId: string) {
    const sessions = await this.db
      .select()
      .from(councilSessions)
      .where(eq(councilSessions.chatSessionId, chatSessionId));

    return sessions;
  }

  /**
   * Get full council details (opinions, debates, synthesis) by council session ID.
   */
  async getDetails(councilSessionId: string) {
    const [opinions, debates, syntheses] = await Promise.all([
      this.db
        .select()
        .from(councilOpinions)
        .where(eq(councilOpinions.councilSessionId, councilSessionId)),
      this.db
        .select()
        .from(councilDebates)
        .where(eq(councilDebates.councilSessionId, councilSessionId)),
      this.db
        .select()
        .from(councilSyntheses)
        .where(eq(councilSyntheses.councilSessionId, councilSessionId)),
    ]);

    return { opinions, debates, syntheses };
  }
}
