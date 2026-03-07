import type { MetricCode } from "../domains/enums.js";

export interface MetricDefinition {
  code: MetricCode;
  version: number;
  formula: string;
  inputs: readonly string[];
  description: string;
}

export const METRIC_DEFINITIONS: readonly MetricDefinition[] = [
  {
    code: "ebitda",
    version: 1,
    formula: "ebit + d&a",
    inputs: ["ebit", "cash_from_operations", "net_income"],
    description: "EBITDA (when DFC available, else EBIT proxy)"
  },
  {
    code: "net_debt",
    version: 1,
    formula: "short_term_debt + long_term_debt - cash_and_equivalents",
    inputs: ["short_term_debt", "long_term_debt", "cash_and_equivalents"],
    description: "Net debt"
  },
  {
    code: "net_working_capital",
    version: 1,
    formula: "current_assets - current_liabilities",
    inputs: ["current_assets", "current_liabilities"],
    description: "Net working capital"
  },
  {
    code: "invested_capital",
    version: 1,
    formula: "net_working_capital + fixed_assets",
    inputs: ["current_assets", "current_liabilities", "fixed_assets"],
    description: "Invested capital"
  },
  {
    code: "enterprise_value",
    version: 1,
    formula: "market_cap + net_debt",
    inputs: ["short_term_debt", "long_term_debt", "cash_and_equivalents"],
    description: "Enterprise value (requires market data)"
  },
  {
    code: "roic",
    version: 1,
    formula: "ebit / invested_capital",
    inputs: ["ebit", "current_assets", "current_liabilities", "fixed_assets"],
    description: "Return on invested capital"
  },
  {
    code: "earnings_yield",
    version: 1,
    formula: "ebit / enterprise_value",
    inputs: ["ebit", "short_term_debt", "long_term_debt", "cash_and_equivalents"],
    description: "Earnings yield"
  },
  {
    code: "roe",
    version: 1,
    formula: "net_income / equity",
    inputs: ["net_income", "equity"],
    description: "Return on equity"
  },
  {
    code: "gross_margin",
    version: 1,
    formula: "gross_profit / revenue",
    inputs: ["gross_profit", "revenue"],
    description: "Gross margin"
  },
  {
    code: "ebit_margin",
    version: 1,
    formula: "ebit / revenue",
    inputs: ["ebit", "revenue"],
    description: "EBIT margin"
  },
  {
    code: "net_margin",
    version: 1,
    formula: "net_income / revenue",
    inputs: ["net_income", "revenue"],
    description: "Net margin"
  },
  {
    code: "debt_to_ebitda",
    version: 1,
    formula: "net_debt / ebitda",
    inputs: ["short_term_debt", "long_term_debt", "cash_and_equivalents", "ebit"],
    description: "Net debt to EBITDA"
  },
  {
    code: "cash_conversion",
    version: 1,
    formula: "cash_from_operations / net_income",
    inputs: ["cash_from_operations", "net_income"],
    description: "Cash conversion (CFO / Net Income)"
  },
  {
    code: "magic_formula_score",
    version: 1,
    formula: "rank(earnings_yield) + rank(roic)",
    inputs: ["ebit", "current_assets", "current_liabilities", "fixed_assets", "short_term_debt", "long_term_debt", "cash_and_equivalents"],
    description: "Magic Formula combined score"
  }
] as const;

export const METRIC_BY_CODE: ReadonlyMap<MetricCode, MetricDefinition> = new Map(
  METRIC_DEFINITIONS.map((def) => [def.code, def])
);
