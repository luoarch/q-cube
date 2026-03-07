import { Inject, Injectable } from "@nestjs/common";
import { eq, sql } from "drizzle-orm";
import type { NodePgDatabase } from "drizzle-orm/node-postgres";
import { DB } from "../database/database.constants.js";
import { issuers, securities, computedMetrics } from "../db/schema.js";
import type * as schema from "../db/schema.js";
import { UNKNOWN_SECTOR, UNKNOWN_SUBSECTOR, universeSchema } from "@q3/shared-contracts";

@Injectable()
export class UniverseService {
  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>
  ) {}

  async getUniverse() {
    // Count distinct issuers with at least 1 security
    const totalRows = await this.db
      .select({
        count: sql<number>`count(distinct ${securities.issuerId})::int`,
      })
      .from(securities);
    const totalStocks = totalRows[0]?.count ?? 0;

    // Get issuer data with sector/subsector
    const issuerRows = await this.db
      .select({
        issuerId: issuers.id,
        legalName: issuers.legalName,
        sector: issuers.sector,
        subsector: issuers.subsector,
      })
      .from(issuers)
      .innerJoin(securities, eq(securities.issuerId, issuers.id));

    // Deduplicate issuers (can appear multiple times due to multiple securities)
    const seen = new Set<string>();
    const uniqueIssuers: typeof issuerRows = [];
    for (const row of issuerRows) {
      if (!seen.has(row.issuerId)) {
        seen.add(row.issuerId);
        uniqueIssuers.push(row);
      }
    }

    // Get market_cap from computed_metrics where available
    const mcRows = await this.db
      .select({
        issuerId: computedMetrics.issuerId,
        value: computedMetrics.value,
      })
      .from(computedMetrics)
      .where(eq(computedMetrics.metricCode, "market_cap"));

    const mcMap = new Map<string, number>();
    for (const row of mcRows) {
      const existing = mcMap.get(row.issuerId) ?? 0;
      const val = row.value ? Number(row.value) : 0;
      if (val > existing) mcMap.set(row.issuerId, val);
    }

    // Group by sector → subsector
    const sectorGroups = new Map<
      string,
      {
        count: number;
        marketCap: number;
        subsectors: Map<string, { count: number; marketCap: number }>;
      }
    >();

    for (const issuer of uniqueIssuers) {
      const sectorName = issuer.sector || UNKNOWN_SECTOR;
      const subsectorName = issuer.subsector || UNKNOWN_SUBSECTOR;
      const mc = mcMap.get(issuer.issuerId) ?? 0;

      if (!sectorGroups.has(sectorName)) {
        sectorGroups.set(sectorName, {
          count: 0,
          marketCap: 0,
          subsectors: new Map(),
        });
      }
      const group = sectorGroups.get(sectorName)!;
      group.count++;
      group.marketCap += mc;

      if (!group.subsectors.has(subsectorName)) {
        group.subsectors.set(subsectorName, { count: 0, marketCap: 0 });
      }
      const sub = group.subsectors.get(subsectorName)!;
      sub.count++;
      sub.marketCap += mc;
    }

    const sectors = Array.from(sectorGroups.entries()).map(
      ([name, group]) => ({
        name,
        count: group.count,
        marketCap: group.marketCap,
        children: Array.from(group.subsectors.entries()).map(
          ([subName, sub]) => ({
            name: subName,
            count: sub.count,
            marketCap: sub.marketCap,
          })
        ),
      })
    );

    return universeSchema.parse({ totalStocks, sectors });
  }
}
