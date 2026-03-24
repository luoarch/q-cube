import { Inject, Injectable, Logger, NotFoundException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { assetDetailSchema, tickerDecisionSchema } from '@q3/shared-contracts';
import { sql } from 'drizzle-orm';

import { DB } from '../database/database.constants.js';

import type * as schema from '../db/schema.js';
import type { NodePgDatabase } from 'drizzle-orm/node-postgres';

@Injectable()
export class AssetService {
  private readonly logger = new Logger(AssetService.name);
  private readonly quantEngineUrl: string;

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
    config: ConfigService,
  ) {
    this.quantEngineUrl = config.get('QUANT_ENGINE_URL') ?? 'http://localhost:8100';
  }

  async getByTicker(ticker: string, _tenantId: string) {
    // Main query: fundamentals from compat view + derived metrics
    const result = await this.db.execute(sql`
      WITH universe AS (
        SELECT
          v.ticker, v.name, v.sector, v.issuer_id, v.security_id,
          v.ebit, v.net_debt, v.ebitda, v.net_working_capital, v.fixed_assets,
          v.roic, v.market_cap, v.avg_daily_volume,
          v.net_margin, v.gross_margin,
          COALESCE(
            v.earnings_yield,
            CASE
              WHEN COALESCE(v.market_cap, 0) + COALESCE(v.net_debt, 0) > 0
              THEN v.ebit / (COALESCE(v.market_cap, 0) + COALESCE(v.net_debt, 0))
            END
          ) AS earnings_yield,
          CASE
            WHEN COALESCE(v.net_working_capital, 0) + COALESCE(v.fixed_assets, 0) != 0
            THEN v.ebit / (COALESCE(v.net_working_capital, 0) + COALESCE(v.fixed_assets, 0))
          END AS return_on_capital,
          PERCENT_RANK() OVER (ORDER BY v.roic NULLS FIRST)            AS pct_roic,
          PERCENT_RANK() OVER (ORDER BY COALESCE(
            v.earnings_yield,
            CASE
              WHEN COALESCE(v.market_cap, 0) + COALESCE(v.net_debt, 0) > 0
              THEN v.ebit / (COALESCE(v.market_cap, 0) + COALESCE(v.net_debt, 0))
            END
          ) NULLS FIRST)  AS pct_ey,
          PERCENT_RANK() OVER (ORDER BY v.gross_margin NULLS FIRST)    AS pct_gm,
          PERCENT_RANK() OVER (ORDER BY v.net_margin NULLS FIRST)      AS pct_nm,
          PERCENT_RANK() OVER (
            ORDER BY CASE
              WHEN COALESCE(v.net_working_capital, 0) + COALESCE(v.fixed_assets, 0) != 0
              THEN v.ebit / (COALESCE(v.net_working_capital, 0) + COALESCE(v.fixed_assets, 0))
            END NULLS FIRST
          ) AS pct_roc
        FROM v_financial_statements_compat v
      ),
      -- Latest price from market snapshots
      latest_price AS (
        SELECT DISTINCT ON (ms.security_id)
          ms.security_id,
          ms.price
        FROM market_snapshots ms
        ORDER BY ms.security_id, ms.fetched_at DESC
      ),
      -- Latest net_income + equity from statement_lines (annual, consolidated)
      latest_fundamentals AS (
        SELECT DISTINCT ON (f.issuer_id, sl.canonical_key)
          f.issuer_id,
          sl.canonical_key,
          sl.normalized_value
        FROM statement_lines sl
        JOIN filings f ON f.id = sl.filing_id
        WHERE sl.canonical_key IN ('net_income', 'equity', 'revenue')
          AND sl.period_type = 'annual'
          AND sl.scope = 'con'
        ORDER BY f.issuer_id, sl.canonical_key, sl.reference_date DESC
      ),
      -- Dividends paid (sum of negative DFC entries with "dividendo"/"juros sobre capital" in label)
      -- Uses the most recent annual period per issuer
      latest_dividends AS (
        SELECT
          f.issuer_id,
          ABS(SUM(sl.normalized_value)) AS dividends_paid
        FROM statement_lines sl
        JOIN filings f ON f.id = sl.filing_id
        WHERE sl.statement_type IN ('DFC_MD', 'DFC_MI')
          AND sl.period_type = 'annual'
          AND sl.scope = 'con'
          AND sl.normalized_value < 0
          AND (
            sl.as_reported_label ILIKE '%dividendo%pago%'
            OR sl.as_reported_label ILIKE '%juros sobre capital próprio%pago%'
            OR sl.as_reported_label ILIKE '%juros sobre capital proprio%pago%'
          )
          AND sl.reference_date = (
            SELECT MAX(sl2.reference_date)
            FROM statement_lines sl2
            JOIN filings f2 ON f2.id = sl2.filing_id
            WHERE f2.issuer_id = f.issuer_id
              AND sl2.period_type = 'annual'
              AND sl2.statement_type IN ('DFC_MD', 'DFC_MI')
          )
        GROUP BY f.issuer_id
      ),
      -- ROE from computed_metrics
      latest_roe AS (
        SELECT DISTINCT ON (cm.issuer_id)
          cm.issuer_id,
          cm.value AS roe
        FROM computed_metrics cm
        WHERE cm.metric_code = 'roe'
          AND cm.period_type = 'annual'
        ORDER BY cm.issuer_id, cm.reference_date DESC
      )
      SELECT
        u.*,
        lp.price,
        ni.normalized_value AS net_income,
        eq.normalized_value AS equity,
        rev.normalized_value AS revenue,
        ld.dividends_paid,
        lr.roe
      FROM universe u
      LEFT JOIN latest_price lp ON lp.security_id = u.security_id
      LEFT JOIN latest_fundamentals ni ON ni.issuer_id = u.issuer_id AND ni.canonical_key = 'net_income'
      LEFT JOIN latest_fundamentals eq ON eq.issuer_id = u.issuer_id AND eq.canonical_key = 'equity'
      LEFT JOIN latest_fundamentals rev ON rev.issuer_id = u.issuer_id AND rev.canonical_key = 'revenue'
      LEFT JOIN latest_dividends ld ON ld.issuer_id = u.issuer_id
      LEFT JOIN latest_roe lr ON lr.issuer_id = u.issuer_id
      WHERE u.ticker = ${ticker}
      LIMIT 1
    `);

    const row = result.rows[0] as Record<string, string | null> | undefined;

    if (!row) {
      throw new NotFoundException(`Asset not found: ${ticker}`);
    }

    const num = (v: string | null | undefined) => (v ? Number(v) : null);

    const marketCap = num(row.market_cap) ?? 0;
    const ebit = num(row.ebit) ?? 0;
    const netDebt = num(row.net_debt) ?? 0;
    const ebitda = num(row.ebitda) ?? 0;
    const roic = num(row.roic) ?? 0;
    const netMargin = num(row.net_margin) ?? 0;
    const grossMargin = num(row.gross_margin) ?? 0;
    const returnOnCapital = num(row.return_on_capital) ?? 0;
    const netDebtToEbitda = ebitda !== 0 ? netDebt / ebitda : null;
    const earningsYield = num(row.earnings_yield) ?? 0;
    const price = num(row.price);
    const netIncome = num(row.net_income);
    const equity = num(row.equity);
    const revenue = num(row.revenue);
    const dividendsPaid = num(row.dividends_paid);
    const roe = num(row.roe);

    // Derived valuation multiples
    const peRatio = netIncome && netIncome > 0 ? marketCap / netIncome : null;
    const pbRatio = equity && equity > 0 ? marketCap / equity : null;
    const dividendYield = dividendsPaid && marketCap > 0 ? dividendsPaid / marketCap : null;

    // Percentile-ranked factors (0-1 scale, relative to universe)
    const pctRoic = num(row.pct_roic) ?? 0;
    const pctEy = num(row.pct_ey) ?? 0;
    const pctGm = num(row.pct_gm) ?? 0;
    const pctNm = num(row.pct_nm) ?? 0;
    const pctRoc = num(row.pct_roc) ?? 0;

    const factors = [
      { name: 'ROIC', value: pctRoic, raw: roic, max: 1 },
      { name: 'Earnings Yield', value: pctEy, raw: earningsYield, max: 1 },
      { name: 'ROE', value: pctRoc, raw: roe ?? 0, max: 1 },
      { name: 'Net Margin', value: pctNm, raw: netMargin, max: 1 },
      { name: 'Gross Margin', value: pctGm, raw: grossMargin, max: 1 },
    ];

    const compositeScore = (pctRoic + pctEy + pctRoc + pctNm + pctGm) / 5;

    // Payout yield: dual-trail analytical surface from computed_metrics
    const payoutYield = await this.buildPayoutYield(row.issuer_id as string);

    return assetDetailSchema.parse({
      ticker,
      name: row.name ?? ticker,
      sector: row.sector || '',
      price,
      change: null,
      marketCap,
      magicFormulaRank: null,
      earningsYield,
      returnOnCapital,
      roic,
      roe,
      grossMargin,
      netMargin,
      netDebtToEbitda: netDebtToEbitda ?? 0,
      dividendYield,
      peRatio,
      pbRatio,
      compositeScore: Math.round(compositeScore * 1000) / 1000,
      factors,
      priceHistory: null,
      payoutYield,
    });
  }

  /**
   * Build the dual-trail payout yield surface from computed_metrics.
   *
   * - Exact trail materializes only if net_buyback_yield or net_payout_yield exists
   * - Free-source trail materializes only if nby_proxy_free or npy_proxy_free exists
   * - dividend_yield participates in composition but does NOT define trail existence
   * - Each trail uses a single anchor date (latest date with trail-specific metrics)
   *
   * payoutYield is the canonical analytical surface.
   * The legacy top-level dividendYield remains for backward compatibility
   * and may differ in source, date, or value.
   */
  private async buildPayoutYield(issuerId: string) {
    const metricsResult = await this.db.execute(sql`
      SELECT metric_code, value::float, reference_date::text
      FROM computed_metrics
      WHERE issuer_id = ${issuerId}
        AND metric_code IN (
          'dividend_yield', 'net_buyback_yield', 'net_payout_yield',
          'nby_proxy_free', 'npy_proxy_free'
        )
      ORDER BY reference_date DESC
    `);

    const metrics = metricsResult.rows as Array<{
      metric_code: string;
      value: number | null;
      reference_date: string;
    }>;

    if (metrics.length === 0) return null;

    // Group by reference_date
    const byDate = new Map<string, Map<string, number | null>>();
    for (const m of metrics) {
      if (!byDate.has(m.reference_date)) {
        byDate.set(m.reference_date, new Map());
      }
      // Keep the first (latest version) per metric+date
      const dateMap = byDate.get(m.reference_date)!;
      if (!dateMap.has(m.metric_code)) {
        dateMap.set(m.metric_code, m.value);
      }
    }

    // Find anchor dates per trail (trail-specific metrics define existence)
    const EXACT_SPECIFIC = ['net_buyback_yield', 'net_payout_yield'];
    const FREE_SPECIFIC = ['nby_proxy_free', 'npy_proxy_free'];

    let exactDate: string | null = null;
    let freeDate: string | null = null;

    // Dates are sorted DESC from the query
    for (const [refDate, dateMetrics] of byDate) {
      if (!exactDate && EXACT_SPECIFIC.some((m) => dateMetrics.has(m))) {
        exactDate = refDate;
      }
      if (!freeDate && FREE_SPECIFIC.some((m) => dateMetrics.has(m))) {
        freeDate = refDate;
      }
      if (exactDate && freeDate) break;
    }

    const getVal = (d: string, code: string): number | null =>
      byDate.get(d)?.get(code) ?? null;

    const exact = exactDate
      ? {
          referenceDate: exactDate,
          dividendYield: getVal(exactDate, 'dividend_yield'),
          netBuybackYield: getVal(exactDate, 'net_buyback_yield'),
          netPayoutYield: getVal(exactDate, 'net_payout_yield'),
          trail: 'exact' as const,
        }
      : null;

    const freeSource = freeDate
      ? {
          referenceDate: freeDate,
          dividendYield: getVal(freeDate, 'dividend_yield'),
          nbyProxyFree: getVal(freeDate, 'nby_proxy_free'),
          npyProxyFree: getVal(freeDate, 'npy_proxy_free'),
          trail: 'free-source' as const,
        }
      : null;

    if (!exact && !freeSource) return null;

    return { exact, freeSource };
  }

  async getTickerDecision(ticker: string) {
    try {
      const res = await fetch(`${this.quantEngineUrl}/decision/${ticker}`);
      if (!res.ok) {
        throw new NotFoundException(`Decision not available for ${ticker}`);
      }
      return await res.json();
    } catch (e) {
      this.logger.warn(`Failed to fetch decision for ${ticker}: ${e}`);
      throw new NotFoundException(`Decision engine unavailable for ${ticker}`);
    }
  }
}
