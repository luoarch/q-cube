import { Inject, Injectable } from '@nestjs/common';
import {
  UNKNOWN_SECTOR,
  dashboardSummarySchema,
  type DashboardSummary,
} from '@q3/shared-contracts';
import { desc, eq, sql } from 'drizzle-orm';

import { CacheService } from '../common/cache.service.js';
import { DB } from '../database/database.constants.js';
import { assets, financialStatements, strategyRuns } from '../db/schema.js';
import { RankingService } from '../ranking/ranking.service.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

const DASHBOARD_CACHE_TTL = 300; // 5 minutes

@Injectable()
export class DashboardService {
  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
    private readonly rankingService: RankingService,
    private readonly cache: CacheService,
  ) {}

  async getSummary(tenantId: string) {
    const cacheKey = `q3:dashboard:${tenantId}`;
    const cached = await this.cache.get<DashboardSummary>(cacheKey);
    if (cached) return cached;
    // KPIs
    const assetCountRows = await this.db
      .select({ count: sql<number>`count(*)::int` })
      .from(assets)
      .where(eq(assets.tenantId, tenantId));
    const totalAssets = assetCountRows[0]?.count ?? 0;

    const avgMetricsRows = await this.db
      .select({
        avgRoic: sql<number>`coalesce(avg(${financialStatements.roic}::float), 0)`,
        avgEY: sql<number>`coalesce(avg(case when ${financialStatements.enterpriseValue}::float > 0 then ${financialStatements.ebit}::float / ${financialStatements.enterpriseValue}::float else 0 end), 0)`,
      })
      .from(financialStatements)
      .where(eq(financialStatements.tenantId, tenantId));
    const avgRoic = avgMetricsRows[0]?.avgRoic ?? 0;
    const avgEY = avgMetricsRows[0]?.avgEY ?? 0;

    const runCountRows = await this.db
      .select({ count: sql<number>`count(*)::int` })
      .from(strategyRuns)
      .where(eq(strategyRuns.tenantId, tenantId));
    const totalRuns = runCountRows[0]?.count ?? 0;

    const kpis = [
      { label: 'Total Assets', value: totalAssets, format: 'number' as const },
      { label: 'Avg ROC', value: Math.round(avgRoic * 10000) / 100, format: 'percent' as const },
      { label: 'Avg EY', value: Math.round(avgEY * 10000) / 100, format: 'percent' as const },
      { label: 'Strategy Runs', value: totalRuns, format: 'number' as const },
    ];

    // Pipeline status from latest strategy run
    const [latestRun] = await this.db
      .select()
      .from(strategyRuns)
      .where(eq(strategyRuns.tenantId, tenantId))
      .orderBy(desc(strategyRuns.createdAt))
      .limit(1);

    const pipelineStatus = latestRun
      ? {
          stage: latestRun.status,
          progress:
            latestRun.status === 'completed' ? 100 : latestRun.status === 'running' ? 50 : 0,
          lastRun: latestRun.createdAt.toISOString(),
        }
      : { stage: 'idle', progress: 0, lastRun: null };

    // Top ranked (use primaryRanking — fully evaluated only)
    const splitRanking = await this.rankingService.getRanking(tenantId);
    const ranking = splitRanking.primaryRanking;
    const topRanked = ranking.slice(0, 5).map((item) => ({
      ticker: item.ticker,
      name: item.name,
      rank: item.rankWithinModel,
      price: item.price,
      change: item.change,
    }));

    // Sector distribution (primary only — fully evaluated universe)
    const sectorDist = new Map<string, number>();
    for (const item of ranking) {
      const s = item.sector || UNKNOWN_SECTOR;
      sectorDist.set(s, (sectorDist.get(s) ?? 0) + 1);
    }
    const sectorDistribution = Array.from(sectorDist.entries()).map(([name, value]) => ({
      name,
      value,
    }));

    const result = dashboardSummarySchema.parse({
      kpis,
      pipelineStatus,
      topRanked,
      sectorDistribution,
    });
    await this.cache.set(cacheKey, result, DASHBOARD_CACHE_TTL);
    return result;
  }
}
