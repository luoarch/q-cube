import {
  Body,
  Controller,
  Get,
  NotFoundException,
  Param,
  ParseUUIDPipe,
  Patch,
  Query,
  UseGuards,
} from '@nestjs/common';
import { aiSuggestionsQuerySchema, updateReviewStatusSchema } from '@q3/shared-contracts';

import { AIService } from './ai.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('ai')
@UseGuards(AuthGuard)
export class AIController {
  constructor(private readonly aiService: AIService) {}

  @Get('suggestions')
  async list(@Query() query: Record<string, string>, @CurrentUser() user: JwtPayload) {
    const parsed = aiSuggestionsQuerySchema.parse(query);
    return this.aiService.listSuggestions(user.tenantId, parsed);
  }

  @Get('suggestions/:id')
  async getById(@Param('id', new ParseUUIDPipe()) id: string, @CurrentUser() user: JwtPayload) {
    const detail = await this.aiService.getSuggestionDetail(id, user.tenantId);
    if (!detail) {
      throw new NotFoundException('AI suggestion not found');
    }
    return detail;
  }

  @Patch('suggestions/:id/review')
  async updateReview(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Body() body: unknown,
    @CurrentUser() user: JwtPayload,
  ) {
    const input = updateReviewStatusSchema.parse(body);
    const updated = await this.aiService.updateReviewStatus(id, user.tenantId, user.sub, input);
    if (!updated) {
      throw new NotFoundException('AI suggestion not found');
    }
    return updated;
  }

  @Get('suggestions/by-entity/:entityId')
  async getByEntity(
    @Param('entityId', new ParseUUIDPipe()) entityId: string,
    @CurrentUser() user: JwtPayload,
  ) {
    return this.aiService.getSuggestionsByEntity(entityId, user.tenantId);
  }
}
