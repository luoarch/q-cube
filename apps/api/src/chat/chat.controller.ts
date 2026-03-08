import {
  Body,
  Controller,
  Get,
  Param,
  ParseUUIDPipe,
  Post,
  UseGuards,
} from '@nestjs/common';
import { createChatSessionSchema, sendMessageSchema } from '@q3/shared-contracts';

import { ChatService } from './chat.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('chat')
@UseGuards(AuthGuard)
export class ChatController {
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

    // TODO: Proxy to ai-assistant for processing (Sprint 4 full integration)
    // For now, return placeholder acknowledging the message
    const assistantMsg = await this.chatService.addMessage(
      sessionId,
      'assistant',
      'Mensagem recebida. O conselho de investimentos sera integrado em breve.',
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
}
