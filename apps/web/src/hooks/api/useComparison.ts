import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { ComparisonMatrix } from '@q3/shared-contracts';

export function useComparison(tickers: string[]) {
  return useQuery<ComparisonMatrix>({
    queryKey: ['comparison', tickers],
    queryFn: () =>
      apiClient.get<ComparisonMatrix>('/compare', { tickers: tickers.join(',') }),
    enabled: tickers.length >= 2,
  });
}
