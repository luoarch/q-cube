import { Inject, Injectable } from "@nestjs/common";
import { eq, desc, sql } from "drizzle-orm";
import type { NodePgDatabase } from "drizzle-orm/node-postgres";
import { DB } from "../database/database.constants.js";
import { CacheService } from "../common/cache.service.js";
import {
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

  private async computeRanking(_tenantId: string) {
    // Read from canonical fundamentals view (global, not tenant-scoped)
    const result = await this.db.execute(sql`
      SELECT ticker, name, sector,
             ebit, net_debt, ebitda, net_working_capital, fixed_assets,
             roic, market_cap, avg_daily_volume
      FROM v_financial_statements_compat
    `);
    const rows = result.rows as Array<{
      ticker: string;
      name: string | null;
      sector: string | null;
      ebit: string | null;
      net_debt: string | null;
      ebitda: string | null;
      net_working_capital: string | null;
      fixed_assets: string | null;
      roic: string | null;
      market_cap: string | null;
      avg_daily_volume: string | null;
    }>;

    // Get latest prices from market_snapshots
    const priceMap = await this.buildPriceMap();

    // Compute earnings yield and return on capital
    const enriched = rows.map((row) => {
      const ebit = row.ebit ? Number(row.ebit) : 0;
      const marketCap = row.market_cap ? Number(row.market_cap) : 0;
      const netDebt = row.net_debt ? Number(row.net_debt) : 0;
      const ev = marketCap > 0 ? marketCap + netDebt : 0;
      const earningsYield = ev > 0 ? ebit / ev : 0;

      const nwc = row.net_working_capital ? Number(row.net_working_capital) : 0;
      const fa = row.fixed_assets ? Number(row.fixed_assets) : 0;
      const capital = nwc + fa;
      const returnOnCapital = capital !== 0 ? ebit / capital : (row.roic ? Number(row.roic) : 0);

      const avgDailyVolume = row.avg_daily_volume ? Number(row.avg_daily_volume) : 0;
      const priceData = priceMap.get(row.ticker);

      return {
        ticker: row.ticker,
        name: row.name ?? row.ticker,
        sector: row.sector || UNKNOWN_SECTOR,
        earningsYield,
        returnOnCapital,
        price: priceData?.price ?? null,
        change: priceData?.change ?? null,
        marketCap,
        quality:
          returnOnCapital >= 0.15 ? "high" : returnOnCapital >= 0.08 ? "medium" : ("low" as const),
        liquidity:
          avgDailyVolume >= 1_000_000
            ? "high"
            : avgDailyVolume >= 100_000
              ? "medium"
              : ("low" as const),
        magicFormulaRank: 0,
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
