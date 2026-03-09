import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { paginatedRankingSchema } from '@q3/shared-contracts';

import { type RankingService } from './ranking.service.js';
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
    @Query('page') page?: string,
    @Query('limit') limit?: string,
    @Query('sector') sector?: string,
    @Query('quality') quality?: string,
    @Query('search') search?: string,
  ) {
    const pageNum = Math.max(1, parseInt(page ?? '1', 10) || 1);
    const parsedLimit = parseInt(limit ?? '50', 10);
    // limit=0 means "return all" (for full-universe 3D scenes)
    const rawLimit = Number.isNaN(parsedLimit) ? 50 : parsedLimit;
    const limitNum = rawLimit === 0 ? 0 : Math.min(100, Math.max(1, rawLimit));

    const all = await this.rankingService.getRanking(user.tenantId);

    // Apply filters
    let filtered = all;
    if (sector) {
      filtered = filtered.filter((item) => item.sector === sector);
    }
    if (quality) {
      filtered = filtered.filter((item) => item.quality === quality);
    }
    if (search) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (item) => item.ticker.toLowerCase().includes(q) || item.name.toLowerCase().includes(q),
      );
    }

    const total = filtered.length;
    const returnAll = limitNum === 0;
    const effectiveLimit = returnAll ? total : limitNum;
    const totalPages = returnAll ? 1 : Math.ceil(total / effectiveLimit);
    const offset = returnAll ? 0 : (pageNum - 1) * effectiveLimit;
    const data = returnAll ? filtered : filtered.slice(offset, offset + effectiveLimit);

    return paginatedRankingSchema.parse({
      data,
      meta: {
        page: returnAll ? 1 : pageNum,
        limit: effectiveLimit,
        total,
        totalPages,
      },
    });
  }
}
