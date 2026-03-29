import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { splitRankingResponseSchema } from '@q3/shared-contracts';

import { RankingService } from './ranking.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('ranking')
@UseGuards(AuthGuard)
export class RankingController {
  constructor(private readonly rankingService: RankingService) {}

  @Get()
  async list(
    @CurrentUser() user: JwtPayload,
    @Query('search') search?: string,
  ) {
    const result = await this.rankingService.getRanking(user.tenantId);

    // Apply search filter to both rankings if provided
    if (search) {
      const q = search.toLowerCase();
      const filter = (item: { ticker: string; name: string }) =>
        item.ticker.toLowerCase().includes(q) || item.name.toLowerCase().includes(q);

      return splitRankingResponseSchema.parse({
        primaryRanking: result.primaryRanking.filter(filter),
        secondaryRanking: result.secondaryRanking.filter(filter),
        summary: result.summary,
      });
    }

    return result;
  }
}
