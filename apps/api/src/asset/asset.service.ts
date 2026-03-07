import { Inject, Injectable, NotFoundException } from "@nestjs/common";
import { and, eq, desc } from "drizzle-orm";
import type { NodePgDatabase } from "drizzle-orm/node-postgres";
import { DB } from "../database/database.constants.js";
import {
  assets,
  financialStatements,
  issuers,
  securities,
  computedMetrics,
} from "../db/schema.js";
import type * as schema from "../db/schema.js";
import { assetDetailSchema } from "@q3/shared-contracts";

@Injectable()
export class AssetService {
  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>
  ) {}

  async getByTicker(ticker: string, tenantId: string) {
    // Try tenant-scoped assets first
    const [asset] = await this.db
      .select()
      .from(assets)
      .where(and(eq(assets.ticker, ticker), eq(assets.tenantId, tenantId)))
      .limit(1);

    // Get financial statement for this asset
    let fs: {
      ebit: string | null;
      enterpriseValue: string | null;
      roic: string | null;
      netMargin: string | null;
      grossMargin: string | null;
      marketCap: string | null;
      ebitda: string | null;
      netDebt: string | null;
      avgDailyVolume: string | null;
    } | null = null;

    if (asset) {
      const [row] = await this.db
        .select({
          ebit: financialStatements.ebit,
          enterpriseValue: financialStatements.enterpriseValue,
          roic: financialStatements.roic,
          netMargin: financialStatements.netMargin,
          grossMargin: financialStatements.grossMargin,
          marketCap: financialStatements.marketCap,
          ebitda: financialStatements.ebitda,
          netDebt: financialStatements.netDebt,
          avgDailyVolume: financialStatements.avgDailyVolume,
        })
        .from(financialStatements)
        .where(eq(financialStatements.assetId, asset.id))
        .orderBy(desc(financialStatements.periodDate))
        .limit(1);
      fs = row ?? null;
    }

    // Try to find issuer via securities ticker if no tenant asset or for enrichment
    const [sec] = await this.db
      .select({
        issuerId: securities.issuerId,
        securityId: securities.id,
      })
      .from(securities)
      .where(eq(securities.ticker, ticker))
      .limit(1);

    let issuer: {
      legalName: string;
      sector: string | null;
      subsector: string | null;
    } | null = null;

    let metricsFromCM: { code: string; value: number }[] = [];

    if (sec) {
      const [iss] = await this.db
        .select({
          legalName: issuers.legalName,
          sector: issuers.sector,
          subsector: issuers.subsector,
        })
        .from(issuers)
        .where(eq(issuers.id, sec.issuerId))
        .limit(1);
      issuer = iss ?? null;

      // Get computed metrics for this issuer
      const cmRows = await this.db
        .select({
          code: computedMetrics.metricCode,
          value: computedMetrics.value,
        })
        .from(computedMetrics)
        .where(eq(computedMetrics.issuerId, sec.issuerId))
        .orderBy(desc(computedMetrics.referenceDate));

      // Deduplicate: keep latest per metric_code
      const seen = new Set<string>();
      for (const row of cmRows) {
        if (!seen.has(row.code)) {
          seen.add(row.code);
          metricsFromCM.push({
            code: row.code,
            value: row.value ? Number(row.value) : 0,
          });
        }
      }
    }

    if (!asset && !issuer) {
      throw new NotFoundException(`Asset not found: ${ticker}`);
    }

    const name = asset?.name ?? issuer?.legalName ?? ticker;
    const sector = asset?.sector || issuer?.sector || "";
    const subsector = asset?.subSector || issuer?.subsector || "";

    const ebit = fs?.ebit ? Number(fs.ebit) : 0;
    const ev = fs?.enterpriseValue ? Number(fs.enterpriseValue) : 0;
    const roic = fs?.roic ? Number(fs.roic) : 0;
    const ebitda = fs?.ebitda ? Number(fs.ebitda) : 0;
    const netDebt = fs?.netDebt ? Number(fs.netDebt) : 0;

    const earningsYield = ev > 0 ? ebit / ev : 0;
    const netDebtToEbitda = ebitda > 0 ? netDebt / ebitda : 0;

    // Find ebit_margin from computed metrics, fallback to net_margin
    const cmMap = new Map(metricsFromCM.map((m) => [m.code, m.value]));
    const ebitMargin =
      cmMap.get("ebit_margin") ??
      (fs?.netMargin ? Number(fs.netMargin) : 0);

    // Build factors array from computed metrics
    const factorDefs = [
      { name: "ROIC", code: "roic", max: 1 },
      { name: "EBIT Margin", code: "ebit_margin", max: 1 },
      { name: "Net Margin", code: "net_margin", max: 1 },
      { name: "Gross Margin", code: "gross_margin", max: 1 },
      { name: "EBITDA", code: "ebitda", max: 0 },
      { name: "Net Debt", code: "net_debt", max: 0 },
    ];
    const factors = factorDefs.map((f) => ({
      name: f.name,
      value: cmMap.get(f.code) ?? (f.code === "roic" ? roic : 0),
      max: f.max || Math.abs(cmMap.get(f.code) ?? 1) * 2,
    }));

    return assetDetailSchema.parse({
      ticker,
      name,
      sector,
      subsector,
      price: null,
      change: null,
      marketCap: fs?.marketCap ? Number(fs.marketCap) : 0,
      magicFormulaRank: null,
      earningsYield,
      returnOnCapital: roic,
      roic,
      ebitMargin,
      netDebtToEbitda,
      dividendYield: null,
      peRatio: null,
      pbRatio: null,
      factors,
      priceHistory: null,
    });
  }
}
