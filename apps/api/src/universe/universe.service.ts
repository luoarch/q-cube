import { Inject, Injectable } from '@nestjs/common';
import { UNKNOWN_SECTOR, universeSchema } from '@q3/shared-contracts';
import { sql } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

@Injectable()
export class UniverseService {
  constructor(@Inject(DB) private readonly db: NodePgDatabase<typeof schema>) {}

  async getUniverse() {
    // Query from compat view which already joins issuers, securities, metrics, and snapshots
    const rows = await this.db.execute(sql`
      SELECT
        ticker,
        name,
        COALESCE(NULLIF(sector, ''), ${UNKNOWN_SECTOR}) AS sector,
        market_cap,
        roic,
        ebit,
        net_margin,
        gross_margin,
        earnings_yield
      FROM v_financial_statements_compat
    `);

    const assets = rows.rows as Array<Record<string, string | null>>;
    const totalStocks = assets.length;

    // Group by sector
    const sectorGroups = new Map<
      string,
      { count: number; marketCap: number }
    >();

    for (const row of assets) {
      const sectorName = row.sector || UNKNOWN_SECTOR;
      const mc = row.market_cap ? Number(row.market_cap) : 0;

      if (!sectorGroups.has(sectorName)) {
        sectorGroups.set(sectorName, { count: 0, marketCap: 0 });
      }
      const group = sectorGroups.get(sectorName)!;
      group.count++;
      group.marketCap += mc;
    }

    const sectors = Array.from(sectorGroups.entries())
      .map(([name, group]) => ({
        name,
        count: group.count,
        marketCap: group.marketCap,
      }))
      .sort((a, b) => b.marketCap - a.marketCap);

    return universeSchema.parse({ totalStocks, sectors });
  }
}
