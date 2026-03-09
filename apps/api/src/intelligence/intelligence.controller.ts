import { BadRequestException, Controller, Get, Param, UseGuards } from '@nestjs/common';

import { IntelligenceService } from './intelligence.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

const TICKER_RE = /^[A-Z0-9]{3,10}$/;

@Controller('intelligence')
@UseGuards(AuthGuard)
export class IntelligenceController {
  constructor(private readonly intelligenceService: IntelligenceService) {}

  @Get(':ticker')
  async getByTicker(@Param('ticker') ticker: string, @CurrentUser() user: JwtPayload) {
    const normalized = ticker.toUpperCase();
    if (!TICKER_RE.test(normalized)) {
      throw new BadRequestException('Invalid ticker format');
    }
    return this.intelligenceService.getByTicker(normalized, user.tenantId);
  }
}
