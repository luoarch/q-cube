import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { Plan2RankingResponse } from '@q3/shared-contracts';

export function useThesisRanking() {
  return useQuery<Plan2RankingResponse>({
    queryKey: ['ranking', 'thesis'],
    queryFn: () => apiClient.get<Plan2RankingResponse>('/thesis/ranking'),
    retry: (failureCount, error) => {
      // Don't retry 404 (no run exists)
      if (error instanceof apiClient.ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });
}
