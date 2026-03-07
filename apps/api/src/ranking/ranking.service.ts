import { Inject, Injectable } from "@nestjs/common";
import { eq, desc, sql } from "drizzle-orm";
import type { NodePgDatabase } from "drizzle-orm/node-postgres";
import { DB } from "../database/database.constants.js";
import { CacheService } from "../common/cache.service.js";
import {
  assets,
  financialStatements,
  issuers,
  marketSnapshots,
  securities
} from "../db/schema.js";
import type * as schema from "../db/schema.js";
import { UNKNOWN_SECTOR, rankingItemSchema } from "@q3/shared-contracts";

const RANKING_CACHE_TTL = 300; // 5 minutes

@Injectable()
export class RankingService {
  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
    private readonly cache: CacheService,
  ) {}

  async getRanking(tenantId: string) {
    const cacheKey = `q3:ranking:${tenantId}`;
    const cached = await this.cache.get<ReturnType<typeof this.computeRanking> extends Promise<infer R> ? R : never>(cacheKey);
    if (cached) return cached;

    const raw = await this.computeRanking(tenantId);
    const result = rankingItemSchema.array().parse(raw);
    await this.cache.set(cacheKey, result, RANKING_CACHE_TTL);
    return result;
  }

  private async computeRanking(tenantId: string) {
    // Get assets with their latest financial statement
    const rows = await this.db
      .select({
        assetId: assets.id,
        ticker: assets.ticker,
        name: assets.name,
        assetSector: assets.sector,
        ebit: financialStatements.ebit,
        enterpriseValue: financialStatements.enterpriseValue,
        roic: financialStatements.roic,
        marketCap: financialStatements.marketCap,
        avgDailyVolume: financialStatements.avgDailyVolume,
      })
      .from(assets)
      .innerJoin(
        financialStatements,
        eq(financialStatements.assetId, assets.id)
      )
      .where(eq(assets.tenantId, tenantId))
      .orderBy(desc(financialStatements.periodDate));

    // Deduplicate: keep only the latest financial statement per asset
    const seen = new Set<string>();
    const unique: typeof rows = [];
    for (const row of rows) {
      if (!seen.has(row.assetId)) {
        seen.add(row.assetId);
        unique.push(row);
      }
    }

    // Try to enrich sector from issuers via securities ticker match
    const sectorMap = await this.buildSectorMap();

    // Try to get latest prices from market_snapshots
    const priceMap = await this.buildPriceMap();

    // Compute earnings yield and return on capital
    const enriched = unique.map((row) => {
      const ebit = row.ebit ? Number(row.ebit) : 0;
      const ev = row.enterpriseValue ? Number(row.enterpriseValue) : 0;
      const earningsYield = ev > 0 ? ebit / ev : 0;
      const returnOnCapital = row.roic ? Number(row.roic) : 0;
      const sector =
        row.assetSector || sectorMap.get(row.ticker) || UNKNOWN_SECTOR;
      const avgDailyVolume = row.avgDailyVolume
        ? Number(row.avgDailyVolume)
        : 0;
      const roic = returnOnCapital;
      const priceData = priceMap.get(row.ticker);

      return {
        ticker: row.ticker,
        name: row.name,
        sector,
        earningsYield,
        returnOnCapital,
        price: priceData?.price ?? null,
        change: priceData?.change ?? null,
        marketCap: row.marketCap ? Number(row.marketCap) : 0,
        quality:
          roic >= 0.15 ? "high" : roic >= 0.08 ? "medium" : ("low" as const),
        liquidity:
          avgDailyVolume >= 1_000_000
            ? "high"
            : avgDailyVolume >= 100_000
              ? "medium"
              : ("low" as const),
        magicFormulaRank: 0, // will be computed below
      };
    });

    // Rank by earningsYield desc
    const byEY = [...enriched]
      .sort((a, b) => b.earningsYield - a.earningsYield)
      .map((item, i) => ({ ticker: item.ticker, eyRank: i + 1 }));

    // Rank by returnOnCapital desc
    const byROC = [...enriched]
      .sort((a, b) => b.returnOnCapital - a.returnOnCapital)
      .map((item, i) => ({ ticker: item.ticker, rocRank: i + 1 }));

    const eyMap = new Map(byEY.map((r) => [r.ticker, r.eyRank]));
    const rocMap = new Map(byROC.map((r) => [r.ticker, r.rocRank]));

    for (const item of enriched) {
      item.magicFormulaRank =
        (eyMap.get(item.ticker) ?? enriched.length) +
        (rocMap.get(item.ticker) ?? enriched.length);
    }

    // Sort by combined rank ascending (1 = best)
    enriched.sort((a, b) => a.magicFormulaRank - b.magicFormulaRank);

    // Re-assign sequential ranks
    enriched.forEach((item, i) => {
      item.magicFormulaRank = i + 1;
    });

    return enriched;
  }

  private async buildPriceMap(): Promise<Map<string, { price: number; change: number }>> {
    const rows = await this.db
      .select({
        ticker: securities.ticker,
        price: marketSnapshots.price,
        fetchedAt: marketSnapshots.fetchedAt,
      })
      .from(marketSnapshots)
      .innerJoin(securities, eq(securities.id, marketSnapshots.securityId))
      .orderBy(desc(marketSnapshots.fetchedAt));

    const map = new Map<string, { price: number; change: number }>();
    for (const row of rows) {
      if (!map.has(row.ticker) && row.price) {
        map.set(row.ticker, { price: Number(row.price), change: 0 });
      }
    }
    return map;
  }

  private async buildSectorMap(): Promise<Map<string, string>> {
    const rows = await this.db
      .select({
        ticker: securities.ticker,
        sector: issuers.sector,
      })
      .from(securities)
      .innerJoin(issuers, eq(issuers.id, securities.issuerId));

    const map = new Map<string, string>();
    for (const row of rows) {
      if (row.sector) {
        map.set(row.ticker, row.sector);
      }
    }
    return map;
  }
}
