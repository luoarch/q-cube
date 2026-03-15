import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { Plan2BreakdownResponse } from '@q3/shared-contracts';

export function useThesisBreakdown(ticker: string | null) {
  return useQuery<Plan2BreakdownResponse>({
    queryKey: ['thesis', 'breakdown', ticker],
    queryFn: () => apiClient.get<Plan2BreakdownResponse>(`/thesis/breakdown/${ticker}`),
    enabled: !!ticker,
    retry: (failureCount, error) => {
      if (error instanceof apiClient.ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });
}
