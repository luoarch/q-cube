import { Inject, Injectable } from "@nestjs/common";
import { and, eq, desc } from "drizzle-orm";
import type { NodePgDatabase } from "drizzle-orm/node-postgres";
import { DB } from "../database/database.constants.js";
import {
  assets,
  financialStatements,
  strategyRuns,
  issuers,
  securities,
} from "../db/schema.js";
import type * as schema from "../db/schema.js";
import { UNKNOWN_SECTOR, strategyResultSchema, portfolioSchema } from "@q3/shared-contracts";

@Injectable()
export class PortfolioService {
  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>
  ) {}

  async getPortfolio(tenantId: string) {
    const emptyPortfolio = {
      totalValue: 0,
      totalReturn: 0,
      holdings: [],
      equityCurve: null,
      factorTilt: [],
    };

    // Find latest completed strategy run
    const [latestRun] = await this.db
      .select()
      .from(strategyRuns)
      .where(
        and(
          eq(strategyRuns.tenantId, tenantId),
          eq(strategyRuns.status, "completed")
        )
      )
      .orderBy(desc(strategyRuns.createdAt))
      .limit(1);

    if (!latestRun?.resultJson) {
      return emptyPortfolio;
    }

    // Extract tickers from result_json
    const parsed = strategyResultSchema.safeParse(latestRun.resultJson);
    if (!parsed.success) return emptyPortfolio;
    const rankedAssets = parsed.data.rankedAssets;

    const tickers = rankedAssets
      .map((a) => (typeof a === "string" ? a : a.ticker))
      .filter(Boolean)
      .slice(0, 10);

    if (tickers.length === 0) {
      return emptyPortfolio;
    }

    // Build sector map from issuers
    const sectorMap = await this.buildSectorMap();

    const weight = 1 / tickers.length;
    const holdings: Array<{
      ticker: string;
      name: string;
      sector: string;
      weight: number;
      value: number;
      return: number;
    }> = [];

    let totalRoic = 0;
    let totalMC = 0;

    for (const ticker of tickers) {
      const [asset] = await this.db
        .select()
        .from(assets)
        .where(and(eq(assets.ticker, ticker), eq(assets.tenantId, tenantId)))
        .limit(1);

      let roic = 0;
      let mc = 0;
      let name = ticker;

      if (asset) {
        name = asset.name;
        const [fs] = await this.db
          .select({
            roic: financialStatements.roic,
            marketCap: financialStatements.marketCap,
          })
          .from(financialStatements)
          .where(eq(financialStatements.assetId, asset.id))
          .orderBy(desc(financialStatements.periodDate))
          .limit(1);

        if (fs) {
          roic = fs.roic ? Number(fs.roic) : 0;
          mc = fs.marketCap ? Number(fs.marketCap) : 0;
        }
      }

      const sector =
        asset?.sector || sectorMap.get(ticker) || UNKNOWN_SECTOR;

      const value = mc * weight;
      totalMC += value;
      totalRoic += roic;

      holdings.push({
        ticker,
        name,
        sector,
        weight: Math.round(weight * 10000) / 100,
        value,
        return: Math.round(roic * 10000) / 100,
      });
    }

    const avgRoic =
      holdings.length > 0 ? totalRoic / holdings.length : 0;

    // Factor tilt: aggregate metrics
    const factorTilt = [
      { name: "ROIC", value: Math.round(avgRoic * 10000) / 100, max: 100 },
      {
        name: "Quality",
        value: Math.round(avgRoic >= 0.15 ? 80 : avgRoic >= 0.08 ? 50 : 20),
        max: 100,
      },
    ];

    return portfolioSchema.parse({
      totalValue: totalMC,
      totalReturn: Math.round(avgRoic * 10000) / 100,
      holdings,
      equityCurve: null,
      factorTilt,
    });
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
