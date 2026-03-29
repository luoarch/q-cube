import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { SplitRankingResponse, RankingItem } from '@q3/shared-contracts';

export function useRanking() {
  return useQuery<SplitRankingResponse>({
    queryKey: ['ranking', 'split'],
    queryFn: async () => {
      return apiClient.get<SplitRankingResponse>('/ranking');
    },
  });
}

/** Convenience: primary items only (for 3D scenes, dashboard, etc.) */
export function usePrimaryRanking(): { data: RankingItem[] | undefined; isLoading: boolean } {
  const query = useRanking();
  return {
    data: query.data?.primaryRanking,
    isLoading: query.isLoading,
  };
}
