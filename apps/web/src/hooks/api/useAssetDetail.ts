import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { AssetDetail } from '@q3/shared-contracts';

export function useAssetDetail(ticker: string | null) {
  return useQuery<AssetDetail>({
    queryKey: ['asset', ticker],
    queryFn: () => apiClient.get<AssetDetail>(`/assets/${ticker}`),
    enabled: !!ticker,
  });
}
