import { Injectable, Logger } from '@nestjs/common';
import { splitRankingResponseSchema } from '@q3/shared-contracts';

import { CacheService } from '../common/cache.service.js';

import type { SplitRankingResponse } from '@q3/shared-contracts';

const QUANT_ENGINE_URL = process.env.QUANT_ENGINE_URL ?? 'http://localhost:8100';
const RANKING_CACHE_TTL = 300;

@Injectable()
export class RankingService {
  private readonly logger = new Logger(RankingService.name);

  constructor(private readonly cache: CacheService) {}

  async getRanking(_tenantId: string): Promise<SplitRankingResponse> {
    const cacheKey = `q3:ranking:split`;
    const cached = await this.cache.get<SplitRankingResponse>(cacheKey);
    if (cached) return cached;

    const result = await this.fetchFromQuantEngine();
    await this.cache.set(cacheKey, result, RANKING_CACHE_TTL);
    return result;
  }

  private async fetchFromQuantEngine(): Promise<SplitRankingResponse> {
    const url = `${QUANT_ENGINE_URL}/ranking`;
    this.logger.log(`Fetching split ranking from ${url}`);

    const res = await fetch(url);
    if (!res.ok) {
      this.logger.error(`Quant engine ranking failed: ${res.status}`);
      return { primaryRanking: [], secondaryRanking: [], summary: { primaryCount: 0, secondaryCount: 0, totalUniverse: 0, missingDataBreakdown: {} } };
    }

    const raw = await res.json();
    return splitRankingResponseSchema.parse(raw);
  }
}
