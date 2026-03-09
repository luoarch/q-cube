import {
  Body,
  Controller,
  Get,
  Inject,
  Logger,
  NotFoundException,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
  UseGuards,
} from '@nestjs/common';
import { createChatSessionSchema, sendMessageSchema } from '@q3/shared-contracts';
import { eq } from 'drizzle-orm';

import { ChatService } from './chat.service.js';
import { CouncilService } from './council.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';
import { DB } from '../database/database.constants.js';
import { tenants } from '../db/schema.js';

import type { JwtPayload } from '../auth/auth.service.js';
import type * as schema from '../db/schema.js';
import type { ChatMode, SendMessage } from '@q3/shared-contracts';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

const AI_ASSISTANT_URL = process.env.AI_ASSISTANT_URL ?? 'http://localhost:8400';

const COUNCIL_MODES = new Set<ChatMode>(['agent_solo', 'roundtable', 'debate', 'comparison']);

@Controller('chat')
@UseGuards(AuthGuard)
export class ChatController {
  private readonly logger = new Logger(ChatController.name);

  constructor(
    private readonly chatService: ChatService,
    private readonly councilService: CouncilService,
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
  ) {}

  @Post('sessions')
  async createSession(@Body() body: unknown, @CurrentUser() user: JwtPayload) {
    const input = createChatSessionSchema.parse(body);
    return this.chatService.createSession(user.tenantId, user.sub, input);
  }

  @Get('sessions')
  async listSessions(@CurrentUser() user: JwtPayload) {
    return this.chatService.listSessions(user.tenantId, user.sub);
  }

  @Post('sessions/:id/messages')
  async sendMessage(
    @Param('id', new ParseUUIDPipe()) sessionId: string,
    @Body() body: unknown,
    @CurrentUser() user: JwtPayload,
  ) {
    const input = sendMessageSchema.parse(body);

    // Persist user message
    await this.chatService.addMessage(sessionId, 'user', input.content);

    // Determine mode: check if message-level mode or session mode requires council
    const mode = input.mode ?? 'free_chat';

    const dailyCostLimit = await this.getTenantCostLimit(user.tenantId);

    if (COUNCIL_MODES.has(mode) && input.tickers?.length) {
      return this.proxyToCouncil(sessionId, user.tenantId, mode, input, dailyCostLimit);
    }

    // Free chat: proxy to AI assistant for tools + RAG + LLM synthesis
    return this.proxyToFreeChat(sessionId, user.tenantId, input.content, dailyCostLimit);
  }

  @Get('sessions/:id/messages')
  async getMessages(
    @Param('id', new ParseUUIDPipe()) sessionId: string,
    @CurrentUser() user: JwtPayload,
  ) {
    return this.chatService.getMessages(sessionId, user.tenantId);
  }

  @Patch('sessions/:id/archive')
  async archiveSession(
    @Param('id', new ParseUUIDPipe()) sessionId: string,
    @CurrentUser() user: JwtPayload,
  ) {
    const result = await this.chatService.archiveSession(sessionId, user.tenantId);
    if (!result) throw new NotFoundException('Session not found');
    return result;
  }

  @Get('budget')
  async getBudget(@CurrentUser() user: JwtPayload) {
    try {
      const res = await fetch(`${AI_ASSISTANT_URL}/budget/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenant_id: user.tenantId }),
      });

      if (!res.ok) {
        this.logger.warn(`Budget status failed: ${res.status}`);
        return { daily_exceeded: false, daily_remaining_usd: 0, daily_limit_usd: 0 };
      }

      return (await res.json()) as Record<string, unknown>;
    } catch (err) {
      this.logger.error(`Budget status error: ${err}`);
      return { daily_exceeded: false, daily_remaining_usd: 0, daily_limit_usd: 0 };
    }
  }

  @Get('sessions/:id/council')
  async getCouncil(
    @Param('id', new ParseUUIDPipe()) sessionId: string,
  ) {
    const sessions = await this.councilService.getByChat(sessionId);
    if (!sessions.length) return { sessions: [] };

    const details = await Promise.all(
      sessions.map(async (s) => ({
        ...s,
        ...(await this.councilService.getDetails(s.id)),
      })),
    );
    return { sessions: details };
  }

  private async proxyToFreeChat(
    sessionId: string,
    tenantId: string,
    message: string,
    dailyCostLimit?: number,
  ) {
    try {
      // Get recent history for conversational context
      const messages = await this.chatService.getMessages(sessionId, tenantId);
      const history = messages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await fetch(`${AI_ASSISTANT_URL}/chat/free`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          history,
          tenant_id: tenantId,
          session_id: sessionId,
          ...(dailyCostLimit != null ? { daily_cost_limit_usd: dailyCostLimit } : {}),
        }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        this.logger.warn(`Free chat proxy failed: ${res.status} ${errorText}`);
        const userMsg = res.status === 429
          ? 'Limite de custo atingido. Inicie uma nova sessao ou tente novamente amanha.'
          : `Erro ao processar mensagem: ${res.status}`;
        return this.chatService.addMessage(sessionId, 'assistant', userMsg);
      }

      const result = (await res.json()) as {
        response: string;
        tools_used: string[];
        provider_used: string;
        model_used: string;
        tokens_used: number;
        cost_usd: number;
      };

      return this.chatService.addMessage(
        sessionId,
        'assistant',
        result.response,
        {
          providerUsed: result.provider_used,
          modelUsed: result.model_used,
          tokensUsed: result.tokens_used,
          costUsd: result.cost_usd,
        },
      );
    } catch (err) {
      this.logger.error(`Free chat proxy error: ${err}`);
      return this.chatService.addMessage(
        sessionId,
        'assistant',
        'Servico de IA indisponivel no momento. Tente novamente mais tarde.',
      );
    }
  }

  private async proxyToCouncil(
    sessionId: string,
    tenantId: string,
    mode: ChatMode,
    input: SendMessage,
    dailyCostLimit?: number,
  ) {
    const tickers = input.tickers!;
    const ticker = tickers[0]!;
    const councilMode = mode === 'agent_solo' ? 'solo' : mode;

    try {
      const res = await fetch(`${AI_ASSISTANT_URL}/council/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: councilMode,
          ticker,
          tickers: mode === 'comparison' ? tickers : undefined,
          agent_ids: input.agentIds ?? null,
          tenant_id: tenantId,
          session_id: sessionId,
          ...(dailyCostLimit != null ? { daily_cost_limit_usd: dailyCostLimit } : {}),
        }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        this.logger.warn(`Council proxy failed: ${res.status} ${errorText}`);
        const userMsg = res.status === 429
          ? 'Limite de custo atingido. Inicie uma nova sessao ou tente novamente amanha.'
          : `Erro ao consultar o conselho de investimentos: ${res.status}`;
        return this.chatService.addMessage(sessionId, 'assistant', userMsg);
      }

      const councilResult = (await res.json()) as Record<string, unknown>;

      // AI assistant returns snake_case; support both conventions
      const opinions = (councilResult.opinions ?? []) as Array<Record<string, unknown>>;

      for (const op of opinions) {
        const agentId = (op.agent_id ?? op.agentId) as string | undefined;
        const verdict = (op.verdict) as string | undefined;
        const confidence = (op.confidence) as number | undefined;
        const thesis = (op.thesis) as string | undefined;
        const modelUsed = (op.model_used ?? op.modelUsed) as string | undefined;
        const providerUsed = (op.provider_used ?? op.providerUsed) as string | undefined;
        const tokensUsed = (op.tokens_used ?? op.tokensUsed) as number | undefined;
        const costUsd = (op.cost_usd ?? op.costUsd) as number | undefined;

        const agentLabel = agentId ? agentId.charAt(0).toUpperCase() + agentId.slice(1) : 'Agent';
        const agentContent = [
          `**${agentLabel}** — ${verdict} (confianca: ${confidence}%)`,
          '',
          thesis ?? '',
        ].join('\n');

        await this.chatService.addMessage(sessionId, 'agent', agentContent, {
          ...(agentId ? { agentId } : {}),
          ...(modelUsed ? { modelUsed } : {}),
          ...(providerUsed ? { providerUsed } : {}),
          ...(tokensUsed ? { tokensUsed } : {}),
          ...(costUsd ? { costUsd } : {}),
        });
      }

      // Persist full council result as a system message for UI rendering
      await this.chatService.addMessage(
        sessionId,
        'system',
        JSON.stringify(councilResult),
      );

      // Persist to dedicated council tables
      const opinionAgentIds = opinions.map(
        (op) => ((op.agent_id ?? op.agentId) as string) ?? 'unknown',
      );
      await this.councilService.persistCouncilResult(
        sessionId,
        tenantId,
        councilMode,
        tickers,
        opinionAgentIds,
        councilResult,
      ).catch((err) => {
        this.logger.error(`Council persistence failed (non-blocking): ${err}`);
      });

      // Persist moderator synthesis as assistant message
      const synthesis = (councilResult.moderator_synthesis ?? councilResult.moderatorSynthesis) as
        Record<string, unknown> | undefined;
      const disclaimer = (councilResult.disclaimer as string) ?? '';
      const synthText = (synthesis?.overall_assessment ?? synthesis?.overallAssessment ?? '') as string;

      const assistantMsg = await this.chatService.addMessage(
        sessionId,
        'assistant',
        `${synthText}\n\n---\n_${disclaimer}_`,
      );

      return assistantMsg;
    } catch (err) {
      this.logger.error(`Council proxy error: ${err}`);
      return this.chatService.addMessage(
        sessionId,
        'assistant',
        'Servico de IA indisponivel no momento. Tente novamente mais tarde.',
      );
    }
  }

  private async getTenantCostLimit(tenantId: string): Promise<number | undefined> {
    try {
      const rows = await this.db
        .select({ limit: tenants.aiDailyCostLimitUsd })
        .from(tenants)
        .where(eq(tenants.id, tenantId))
        .limit(1);

      const raw = rows[0]?.limit;
      return raw != null ? Number(raw) : undefined;
    } catch (err) {
      this.logger.warn(`Failed to fetch tenant cost limit: ${err}`);
      return undefined;
    }
  }
}
