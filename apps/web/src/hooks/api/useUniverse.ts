import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { UniverseData } from '@q3/shared-contracts';

export function useUniverse() {
  return useQuery<UniverseData>({
    queryKey: ['universe'],
    queryFn: () => apiClient.get<UniverseData>('/universe'),
  });
}
