import { BadRequestException, Controller, Get, Query, UseGuards } from '@nestjs/common';

import { ComparisonService } from './comparison.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('compare')
@UseGuards(AuthGuard)
export class ComparisonController {
  constructor(private readonly comparisonService: ComparisonService) {}

  @Get()
  async compare(
    @Query('tickers') tickersParam: string,
    @CurrentUser() user: JwtPayload,
  ) {
    if (!tickersParam) {
      throw new BadRequestException('tickers query parameter is required (e.g., ?tickers=WEGE3,ITUB4)');
    }

    const tickers = tickersParam
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);

    if (tickers.length < 2 || tickers.length > 3) {
      throw new BadRequestException('Provide 2-3 tickers separated by commas');
    }

    return this.comparisonService.compare(tickers, user.tenantId);
  }
}
