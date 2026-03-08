import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { BacktestRunResponse } from '@q3/shared-contracts';

export function useStrategyRun(runId: string | null) {
  return useQuery<BacktestRunResponse>({
    queryKey: ['strategy-run', runId],
    queryFn: () => apiClient.get<BacktestRunResponse>(`/strategy-runs/${runId}`),
    enabled: !!runId,
  });
}
