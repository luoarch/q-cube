import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { PaginatedRanking, RankingItem } from '@q3/shared-contracts';

export function useRanking() {
  return useQuery<RankingItem[]>({
    queryKey: ['ranking', 'full'],
    queryFn: async () => {
      const res = await apiClient.get<PaginatedRanking>('/ranking', {
        limit: '0',
      });
      return res.data;
    },
  });
}
