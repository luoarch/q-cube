import { useQuery } from '@tanstack/react-query';

import { apiClient } from './apiClient';

// ---------------------------------------------------------------------------
// Types (mirrors quant-engine monitoring.py dataclasses)
// ---------------------------------------------------------------------------

export interface DimensionCoverage {
  dimension_key: string;
  total_issuers: number;
  source_type_counts: Record<string, number>;
  confidence_counts: Record<string, number>;
  non_default_pct: number;
}

export interface MonitoringSummary {
  run_id: string;
  total_eligible: number;
  dimension_coverage: DimensionCoverage[];
  provenance_mix: Record<string, number>;
  provenance_mix_pct: Record<string, number>;
  confidence_distribution: Record<string, number>;
  evidence_quality_distribution: Record<string, number>;
  evidence_quality_pct: Record<string, number>;
}

export interface DriftDetail {
  issuer_id: string;
  ticker: string;
  old_bucket: string | null;
  new_bucket: string | null;
  fragility_delta: number | null;
  old_rank: number | null;
  new_rank: number | null;
  rank_delta: number | null;
}

export interface DriftSummary {
  current_run_id: string;
  previous_run_id: string;
  bucket_changes: number;
  bucket_change_details: DriftDetail[];
  top10_entered: string[];
  top10_exited: string[];
  top20_entered: string[];
  top20_exited: string[];
  new_issuers: string[];
  dropped_issuers: string[];
  fragility_delta_avg: number | null;
  fragility_delta_max: number | null;
  fragility_delta_min: number | null;
  error?: string;
}

export interface StaleRubric {
  issuer_id: string;
  ticker: string;
  dimension_key: string;
  source_type: string;
  confidence: string;
  assessed_at: string | null;
  age_days: number | null;
  assessed_by: string | null;
}

export interface RubricAgingReport {
  stale_threshold_days: number;
  total_active_rubrics: number;
  stale_count: number;
  stale_pct: number;
  stale_by_dimension: Record<string, number>;
  stale_rubrics: StaleRubric[];
}

export interface ReviewItem {
  issuer_id: string;
  ticker: string;
  dimension_key: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  reasons: string[];
  current_score: number;
  source_type: string;
  confidence: string;
  age_days: number | null;
}

export interface ReviewQueueResponse {
  total_items: number;
  high_priority: number;
  medium_priority: number;
  low_priority: number;
  items: ReviewItem[];
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useMonitoringSummary() {
  return useQuery<MonitoringSummary>({
    queryKey: ['thesis', 'monitoring'],
    queryFn: () => apiClient.get<MonitoringSummary>('/thesis/monitoring'),
    retry: (failureCount, error) => {
      if (error instanceof apiClient.ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });
}

export function useDrift() {
  return useQuery<DriftSummary>({
    queryKey: ['thesis', 'monitoring', 'drift'],
    queryFn: () => apiClient.get<DriftSummary>('/thesis/monitoring/drift'),
    retry: (failureCount, error) => {
      if (error instanceof apiClient.ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });
}

export function useRubricAging(staleDays = 30) {
  return useQuery<RubricAgingReport>({
    queryKey: ['thesis', 'monitoring', 'aging', staleDays],
    queryFn: () =>
      apiClient.get<RubricAgingReport>('/thesis/monitoring/rubric-aging', {
        stale_days: String(staleDays),
      }),
  });
}

export function useReviewQueue(staleDays = 30) {
  return useQuery<ReviewQueueResponse>({
    queryKey: ['thesis', 'monitoring', 'review-queue', staleDays],
    queryFn: () =>
      apiClient.get<ReviewQueueResponse>('/thesis/monitoring/review-queue', {
        stale_days: String(staleDays),
      }),
  });
}

// ---------------------------------------------------------------------------
// Alerts (F3.3)
// ---------------------------------------------------------------------------

export interface AlertItem {
  code: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  title: string;
  message: string;
  metric_value: number;
  threshold: number;
  context: Record<string, unknown>;
}

export interface AlertsResponse {
  run_id: string;
  alert_count: number;
  critical_count: number;
  warning_count: number;
  alerts: AlertItem[];
}

export function useMonitoringAlerts(staleDays = 30) {
  return useQuery<AlertsResponse>({
    queryKey: ['thesis', 'monitoring', 'alerts', staleDays],
    queryFn: () =>
      apiClient.get<AlertsResponse>('/thesis/monitoring/alerts', {
        stale_days: String(staleDays),
      }),
    retry: (failureCount, error) => {
      if (error instanceof apiClient.ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });
}
