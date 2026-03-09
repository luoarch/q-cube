import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type {
  CreateStrategyRunResponse,
  StrategyRunResponse,
  StrategyType,
} from '@q3/shared-contracts';

export function useStrategyRuns() {
  return useQuery<StrategyRunResponse[]>({
    queryKey: ['strategy-runs'],
    queryFn: () => apiClient.get<StrategyRunResponse[]>('/strategy-runs'),
    refetchInterval: 5000,
  });
}

export function useCreateStrategyRun() {
  const qc = useQueryClient();
  return useMutation<CreateStrategyRunResponse, Error, { strategy: StrategyType }>({
    mutationFn: (input) => apiClient.post<CreateStrategyRunResponse>('/strategy-runs', input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strategy-runs'] });
      qc.invalidateQueries({ queryKey: ['ranking'] });
    },
  });
}
