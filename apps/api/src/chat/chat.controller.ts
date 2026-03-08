import {
  Body,
  Controller,
  Get,
  Logger,
  Param,
  ParseUUIDPipe,
  Post,
  UseGuards,
} from '@nestjs/common';
import { createChatSessionSchema, sendMessageSchema } from '@q3/shared-contracts';

import { ChatService } from './chat.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { ChatMode, SendMessage } from '@q3/shared-contracts';
import type { JwtPayload } from '../auth/auth.service.js';

const AI_ASSISTANT_URL = process.env.AI_ASSISTANT_URL ?? 'http://localhost:8400';

const COUNCIL_MODES = new Set<ChatMode>(['agent_solo', 'roundtable', 'debate', 'comparison']);

@Controller('chat')
@UseGuards(AuthGuard)
export class ChatController {
  private readonly logger = new Logger(ChatController.name);

  constructor(private readonly chatService: ChatService) {}

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

    if (COUNCIL_MODES.has(mode) && input.tickers?.length) {
      return this.proxyToCouncil(sessionId, user.tenantId, mode, input);
    }

    // Free chat: placeholder response (will be replaced with RAG + tools integration)
    const assistantMsg = await this.chatService.addMessage(
      sessionId,
      'assistant',
      'Mensagem recebida. Use um modo de conselho (mesa redonda, agente solo, debate) com tickers para ativar a analise.',
    );

    return assistantMsg;
  }

  @Get('sessions/:id/messages')
  async getMessages(
    @Param('id', new ParseUUIDPipe()) sessionId: string,
    @CurrentUser() user: JwtPayload,
  ) {
    return this.chatService.getMessages(sessionId, user.tenantId);
  }

  private async proxyToCouncil(
    sessionId: string,
    tenantId: string,
    mode: ChatMode,
    input: SendMessage,
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
        }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        this.logger.warn(`Council proxy failed: ${res.status} ${errorText}`);
        return this.chatService.addMessage(
          sessionId,
          'assistant',
          `Erro ao consultar o conselho de investimentos: ${res.status}`,
        );
      }

      const councilResult = (await res.json()) as Record<string, unknown>;

      // Persist each agent opinion as a separate message
      const opinions = (councilResult.opinions ?? []) as Array<{
        agentId?: string;
        verdict?: string;
        thesis?: string;
        confidence?: number;
        modelUsed?: string;
      }>;

      for (const opinion of opinions) {
        const agentContent = [
          `**${opinion.agentId}** — ${opinion.verdict} (confianca: ${opinion.confidence}%)`,
          '',
          opinion.thesis ?? '',
        ].join('\n');

        await this.chatService.addMessage(sessionId, 'agent', agentContent, {
          ...(opinion.agentId ? { agentId: opinion.agentId } : {}),
          ...(opinion.modelUsed ? { modelUsed: opinion.modelUsed } : {}),
        });
      }

      // Persist moderator synthesis
      const synthesis = councilResult.moderator_synthesis as {
        overallAssessment?: string;
        overall_assessment?: string;
      } | undefined;
      const disclaimer = (councilResult.disclaimer as string) ?? '';
      const synthText = synthesis?.overallAssessment ?? synthesis?.overall_assessment ?? '';

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
}
