import { z } from 'zod';

export const statementTypeSchema = z.enum(['DRE', 'BPA', 'BPP', 'DFC_MD', 'DFC_MI', 'DMPL', 'DVA']);

export const periodTypeSchema = z.enum(['annual', 'quarterly']);

export const filingTypeSchema = z.enum(['DFP', 'ITR', 'FCA']);

export const filingStatusSchema = z.enum([
  'pending',
  'processing',
  'completed',
  'failed',
  'superseded',
]);

export const batchStatusSchema = z.enum([
  'pending',
  'downloading',
  'processing',
  'completed',
  'failed',
]);

export const scopeTypeSchema = z.enum(['con', 'ind']);

export const sourceProviderSchema = z.enum(['cvm', 'brapi', 'dados_de_mercado', 'manual', 'yahoo']);

export const metricCodeSchema = z.enum([
  'ebitda',
  'net_debt',
  'net_working_capital',
  'invested_capital',
  'enterprise_value',
  'roic',
  'earnings_yield',
  'roe',
  'gross_margin',
  'ebit_margin',
  'net_margin',
  'debt_to_ebitda',
  'cash_conversion',
  'magic_formula_score',
]);

export type StatementType = z.infer<typeof statementTypeSchema>;
export type PeriodType = z.infer<typeof periodTypeSchema>;
export type FilingType = z.infer<typeof filingTypeSchema>;
export type FilingStatus = z.infer<typeof filingStatusSchema>;
export type BatchStatus = z.infer<typeof batchStatusSchema>;
export type ScopeType = z.infer<typeof scopeTypeSchema>;
export type SourceProvider = z.infer<typeof sourceProviderSchema>;
export type MetricCode = z.infer<typeof metricCodeSchema>;
