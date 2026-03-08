import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { PortfolioData } from '@q3/shared-contracts';

export function usePortfolio() {
  return useQuery<PortfolioData>({
    queryKey: ['portfolio'],
    queryFn: () => apiClient.get<PortfolioData>('/portfolio'),
  });
}
