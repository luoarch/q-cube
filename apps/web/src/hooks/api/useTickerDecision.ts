import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { TickerDecision } from '@q3/shared-contracts';

export function useTickerDecision(ticker: string | null) {
  return useQuery<TickerDecision>({
    queryKey: ['decision', ticker],
    queryFn: () => apiClient.get<TickerDecision>(`/assets/${ticker}/decision`),
    enabled: !!ticker,
    staleTime: 60_000,
    retry: false,
  });
}
