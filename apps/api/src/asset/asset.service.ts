import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { assetDetailSchema } from '@q3/shared-contracts';
import { sql } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

@Injectable()
export class AssetService {
  constructor(@Inject(DB) private readonly db: NodePgDatabase<typeof schema>) {}

  async getByTicker(ticker: string, _tenantId: string) {
    // CTE computes PERCENT_RANK across the full universe, then filters
    const result = await this.db.execute(sql`
      WITH universe AS (
        SELECT
          ticker, name, sector,
          ebit, net_debt, ebitda, net_working_capital, fixed_assets,
          roic, market_cap, avg_daily_volume,
          net_margin, gross_margin, earnings_yield,
          -- ROC: EBIT / (NWC + Fixed Assets), NULL when denominator is 0 or NULL
          CASE
            WHEN COALESCE(net_working_capital, 0) + COALESCE(fixed_assets, 0) != 0
            THEN ebit / (COALESCE(net_working_capital, 0) + COALESCE(fixed_assets, 0))
          END AS return_on_capital,
          -- Percentile ranks (0 = worst, 1 = best in universe)
          PERCENT_RANK() OVER (ORDER BY roic NULLS FIRST)            AS pct_roic,
          PERCENT_RANK() OVER (ORDER BY earnings_yield NULLS FIRST)  AS pct_ey,
          PERCENT_RANK() OVER (ORDER BY gross_margin NULLS FIRST)    AS pct_gm,
          PERCENT_RANK() OVER (ORDER BY net_margin NULLS FIRST)      AS pct_nm,
          PERCENT_RANK() OVER (
            ORDER BY CASE
              WHEN COALESCE(net_working_capital, 0) + COALESCE(fixed_assets, 0) != 0
              THEN ebit / (COALESCE(net_working_capital, 0) + COALESCE(fixed_assets, 0))
            END NULLS FIRST
          ) AS pct_roc
        FROM v_financial_statements_compat
      )
      SELECT * FROM universe WHERE ticker = ${ticker} LIMIT 1
    `);

    const row = result.rows[0] as
      | {
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
          net_margin: string | null;
          gross_margin: string | null;
          earnings_yield: string | null;
          return_on_capital: string | null;
          pct_roic: string | null;
          pct_ey: string | null;
          pct_gm: string | null;
          pct_nm: string | null;
          pct_roc: string | null;
        }
      | undefined;

    if (!row) {
      throw new NotFoundException(`Asset not found: ${ticker}`);
    }

    const marketCap = row.market_cap ? Number(row.market_cap) : 0;
    const netDebt = row.net_debt ? Number(row.net_debt) : 0;
    const ebitda = row.ebitda ? Number(row.ebitda) : 0;
    const roic = row.roic ? Number(row.roic) : 0;
    const earningsYield = row.earnings_yield ? Number(row.earnings_yield) : 0;
    const netMargin = row.net_margin ? Number(row.net_margin) : 0;
    const grossMargin = row.gross_margin ? Number(row.gross_margin) : 0;
    const returnOnCapital = row.return_on_capital ? Number(row.return_on_capital) : 0;
    const netDebtToEbitda = ebitda > 0 ? netDebt / ebitda : 0;

    // Percentile-ranked factors (0-1 scale, relative to universe)
    const pctRoic = row.pct_roic ? Number(row.pct_roic) : 0;
    const pctEy = row.pct_ey ? Number(row.pct_ey) : 0;
    const pctGm = row.pct_gm ? Number(row.pct_gm) : 0;
    const pctNm = row.pct_nm ? Number(row.pct_nm) : 0;
    const pctRoc = row.pct_roc ? Number(row.pct_roc) : 0;

    const factors = [
      { name: 'ROIC', value: pctRoic, raw: roic, max: 1 },
      { name: 'Earnings Yield', value: pctEy, raw: earningsYield, max: 1 },
      { name: 'ROC', value: pctRoc, raw: returnOnCapital, max: 1 },
      { name: 'Net Margin', value: pctNm, raw: netMargin, max: 1 },
      { name: 'Gross Margin', value: pctGm, raw: grossMargin, max: 1 },
    ];

    const compositeScore = (pctRoic + pctEy + pctRoc + pctNm + pctGm) / 5;

    return assetDetailSchema.parse({
      ticker,
      name: row.name ?? ticker,
      sector: row.sector || '',
      price: null,
      change: null,
      marketCap,
      magicFormulaRank: null,
      earningsYield,
      returnOnCapital,
      roic,
      grossMargin,
      netMargin,
      netDebtToEbitda,
      dividendYield: null,
      peRatio: null,
      pbRatio: null,
      compositeScore: Math.round(compositeScore * 1000) / 1000,
      factors,
      priceHistory: null,
    });
  }
}
