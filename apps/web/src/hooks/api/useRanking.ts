import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { PaginatedRanking, RankingItem, DataProvenance } from '@q3/shared-contracts';

interface RankingResult {
  data: RankingItem[];
  provenance: DataProvenance | null;
}

export function useRanking() {
  return useQuery<RankingResult>({
    queryKey: ['ranking', 'full'],
    queryFn: async () => {
      const res = await apiClient.get<PaginatedRanking>('/ranking', {
        limit: '0',
      });
      return { data: res.data, provenance: res.provenance ?? null };
    },
  });
}
