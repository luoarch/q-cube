import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { DashboardSummary } from '@q3/shared-contracts';

export function useDashboard() {
  return useQuery<DashboardSummary>({
    queryKey: ['dashboard'],
    queryFn: () => apiClient.get<DashboardSummary>('/dashboard/summary'),
  });
}
