import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { BacktestRunResponse, CreateBacktestRunInput } from '@q3/shared-contracts';

export function useBacktestRuns() {
  return useQuery<BacktestRunResponse[]>({
    queryKey: ['backtest-runs'],
    queryFn: () => apiClient.get<BacktestRunResponse[]>('/backtest-runs'),
  });
}

export function useBacktestRun(runId: string | null) {
  return useQuery<BacktestRunResponse>({
    queryKey: ['backtest-run', runId],
    queryFn: () => apiClient.get<BacktestRunResponse>(`/backtest-runs/${runId}`),
    enabled: !!runId,
  });
}

export function useCreateBacktestRun() {
  const qc = useQueryClient();
  return useMutation<BacktestRunResponse, Error, Omit<CreateBacktestRunInput, 'tenantId'>>({
    mutationFn: (input) => apiClient.post<BacktestRunResponse>('/backtest-runs', input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backtest-runs'] }),
  });
}
