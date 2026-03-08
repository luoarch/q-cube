import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { CompanyIntelligence } from '@q3/shared-contracts';

export function useIntelligence(ticker: string | null) {
  return useQuery<CompanyIntelligence>({
    queryKey: ['intelligence', ticker],
    queryFn: () => apiClient.get<CompanyIntelligence>(`/intelligence/${ticker}`),
    enabled: !!ticker,
  });
}
