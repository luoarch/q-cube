import type { StatementType } from '../domains/enums.js';

export interface CanonicalKeyEntry {
  key: string;
  cvmCode: string;
  statementType: StatementType;
  sign: '+' | '-' | '±';
  description: string;
}

export const CANONICAL_KEYS: readonly CanonicalKeyEntry[] = [
  // DRE
  {
    key: 'revenue',
    cvmCode: '3.01',
    statementType: 'DRE',
    sign: '+',
    description: 'Receita Líquida',
  },
  {
    key: 'cost_of_goods_sold',
    cvmCode: '3.02',
    statementType: 'DRE',
    sign: '-',
    description: 'Custo dos Bens/Serviços',
  },
  {
    key: 'gross_profit',
    cvmCode: '3.03',
    statementType: 'DRE',
    sign: '+',
    description: 'Resultado Bruto',
  },
  {
    key: 'operating_expenses',
    cvmCode: '3.04',
    statementType: 'DRE',
    sign: '-',
    description: 'Despesas Operacionais',
  },
  {
    key: 'ebit',
    cvmCode: '3.05',
    statementType: 'DRE',
    sign: '+',
    description: 'Resultado Antes do Resultado Financeiro',
  },
  {
    key: 'financial_result',
    cvmCode: '3.06',
    statementType: 'DRE',
    sign: '±',
    description: 'Resultado Financeiro',
  },
  {
    key: 'ebt',
    cvmCode: '3.07',
    statementType: 'DRE',
    sign: '+',
    description: 'Resultado Antes dos Tributos',
  },
  { key: 'income_tax', cvmCode: '3.08', statementType: 'DRE', sign: '-', description: 'IR/CSLL' },
  {
    key: 'net_income',
    cvmCode: '3.11',
    statementType: 'DRE',
    sign: '+',
    description: 'Lucro Líquido',
  },
  // BPA
  {
    key: 'total_assets',
    cvmCode: '1',
    statementType: 'BPA',
    sign: '+',
    description: 'Ativo Total',
  },
  {
    key: 'current_assets',
    cvmCode: '1.01',
    statementType: 'BPA',
    sign: '+',
    description: 'Ativo Circulante',
  },
  {
    key: 'cash_and_equivalents',
    cvmCode: '1.01.01',
    statementType: 'BPA',
    sign: '+',
    description: 'Caixa e Equivalentes',
  },
  {
    key: 'non_current_assets',
    cvmCode: '1.02',
    statementType: 'BPA',
    sign: '+',
    description: 'Ativo Não Circulante',
  },
  {
    key: 'fixed_assets',
    cvmCode: '1.02.03',
    statementType: 'BPA',
    sign: '+',
    description: 'Imobilizado',
  },
  {
    key: 'intangible_assets',
    cvmCode: '1.02.04',
    statementType: 'BPA',
    sign: '+',
    description: 'Intangível',
  },
  // BPP
  {
    key: 'total_liabilities',
    cvmCode: '2',
    statementType: 'BPP',
    sign: '+',
    description: 'Passivo Total + PL',
  },
  {
    key: 'current_liabilities',
    cvmCode: '2.01',
    statementType: 'BPP',
    sign: '+',
    description: 'Passivo Circulante',
  },
  {
    key: 'short_term_debt',
    cvmCode: '2.01.04',
    statementType: 'BPP',
    sign: '+',
    description: 'Empréstimos CP',
  },
  {
    key: 'non_current_liabilities',
    cvmCode: '2.02',
    statementType: 'BPP',
    sign: '+',
    description: 'Passivo Não Circulante',
  },
  {
    key: 'long_term_debt',
    cvmCode: '2.02.01',
    statementType: 'BPP',
    sign: '+',
    description: 'Empréstimos LP',
  },
  {
    key: 'equity',
    cvmCode: '2.03',
    statementType: 'BPP',
    sign: '+',
    description: 'Patrimônio Líquido',
  },
  // DFC_MD
  {
    key: 'cash_from_operations',
    cvmCode: '6.01',
    statementType: 'DFC_MD',
    sign: '+',
    description: 'Caixa Operacional',
  },
  {
    key: 'cash_from_investing',
    cvmCode: '6.02',
    statementType: 'DFC_MD',
    sign: '-',
    description: 'Caixa Investimento',
  },
  {
    key: 'cash_from_financing',
    cvmCode: '6.03',
    statementType: 'DFC_MD',
    sign: '±',
    description: 'Caixa Financiamento',
  },
] as const;

export const CVM_CODE_TO_CANONICAL: ReadonlyMap<string, string> = new Map(
  CANONICAL_KEYS.map((entry) => [entry.cvmCode, entry.key]),
);

export const CANONICAL_TO_CVM_CODE: ReadonlyMap<string, string> = new Map(
  CANONICAL_KEYS.map((entry) => [entry.key, entry.cvmCode]),
);
