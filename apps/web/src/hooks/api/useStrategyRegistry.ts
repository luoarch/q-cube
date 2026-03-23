import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

export interface StrategyRegistryEntry {
  strategyKey: string;
  strategyFingerprint: string;
  strategyType: string;
  role: 'CONTROL' | 'CANDIDATE' | 'FRONTRUNNER';
  promotionStatus: 'NOT_EVALUATED' | 'BLOCKED' | 'PROMOTED' | 'REJECTED';
  evidenceSummary: string;
  isSharpeAvg: number | null;
  oosSharpeAvg: number | null;
  promotionChecks: Record<string, unknown>;
  configJson: Record<string, unknown>;
}

export function useStrategyRegistry() {
  return useQuery<StrategyRegistryEntry[]>({
    queryKey: ['strategy-registry'],
    queryFn: () => apiClient.get<StrategyRegistryEntry[]>('/strategy-runs/registry'),
    staleTime: 60_000,
  });
}

export function getStatusLabel(role: string, promotionStatus: string): string {
  if (role === 'CONTROL' && promotionStatus === 'REJECTED') return 'Rejected control';
  if (role === 'FRONTRUNNER' && promotionStatus === 'BLOCKED') return 'Research frontrunner — promotion blocked';
  if (promotionStatus === 'PROMOTED') return 'Empirically promoted';
  if (promotionStatus === 'NOT_EVALUATED') return 'Research candidate — not yet validated';
  if (promotionStatus === 'REJECTED') return 'Rejected';
  if (promotionStatus === 'BLOCKED') return 'Promotion blocked';
  return `${role} / ${promotionStatus}`;
}

export function getStatusColor(promotionStatus: string): string {
  switch (promotionStatus) {
    case 'PROMOTED': return '#22c55e';
    case 'BLOCKED': return '#fbbf24';
    case 'REJECTED': return '#ef4444';
    case 'NOT_EVALUATED': return '#94a3b8';
    default: return '#94a3b8';
  }
}
