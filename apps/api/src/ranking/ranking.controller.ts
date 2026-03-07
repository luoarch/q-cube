import { Controller, Get, Query, UseGuards } from "@nestjs/common";
import { AuthGuard } from "../auth/auth.guard.js";
import { CurrentUser } from "../auth/current-user.decorator.js";
import type { JwtPayload } from "../auth/auth.service.js";
import { RankingService } from "./ranking.service.js";
import { paginatedRankingSchema } from "@q3/shared-contracts";

@Controller("ranking")
@UseGuards(AuthGuard)
export class RankingController {
  constructor(private readonly rankingService: RankingService) {}

  @Get()
  async list(
    @CurrentUser() user: JwtPayload,
    @Query("page") page?: string,
    @Query("limit") limit?: string,
    @Query("sector") sector?: string,
    @Query("quality") quality?: string,
    @Query("search") search?: string,
  ) {
    const pageNum = Math.max(1, parseInt(page ?? "1", 10) || 1);
    const limitNum = Math.min(100, Math.max(1, parseInt(limit ?? "50", 10) || 50));

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
        (item) =>
          item.ticker.toLowerCase().includes(q) ||
          item.name.toLowerCase().includes(q),
      );
    }

    const total = filtered.length;
    const totalPages = Math.ceil(total / limitNum);
    const offset = (pageNum - 1) * limitNum;
    const data = filtered.slice(offset, offset + limitNum);

    return paginatedRankingSchema.parse({
      data,
      meta: {
        page: pageNum,
        limit: limitNum,
        total,
        totalPages,
      },
    });
  }
}
