import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { RubricScoreResponse, RubricScoreInput } from '@q3/shared-contracts';

interface RubricsResponse {
  issuerId: string;
  ticker: string;
  rubrics: RubricScoreResponse[];
}

export function useThesisRubrics(ticker: string | null) {
  return useQuery<RubricsResponse>({
    queryKey: ['thesis', 'rubrics', ticker],
    queryFn: () => apiClient.get<RubricsResponse>(`/thesis/rubrics/${ticker}`),
    enabled: !!ticker,
    retry: (failureCount, error) => {
      if (error instanceof apiClient.ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });
}

export function useUpsertRubric() {
  const queryClient = useQueryClient();
  return useMutation<RubricScoreResponse, Error, RubricScoreInput>({
    mutationFn: (input) => apiClient.post<RubricScoreResponse>('/thesis/rubrics', input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['thesis', 'rubrics'] });
    },
  });
}

export interface RubricSuggestion {
  suggestionId: string;
  issuerId: string;
  ticker: string;
  dimensionKey: string;
  suggestedScore: number;
  confidence: string;
  rationale: string;
  evidenceRef: string;
  keySignals: string[];
  uncertaintyFactors: string[];
  modelUsed: string;
  promptVersion: string;
  costUsd: number;
}

interface SuggestInput {
  ticker: string;
  dimension?: string;
}

export function useSuggestRubric() {
  return useMutation<RubricSuggestion, Error, SuggestInput>({
    mutationFn: ({ ticker, dimension }) => {
      const params = dimension ? `?dimension=${dimension}` : '';
      return apiClient.post<RubricSuggestion>(`/thesis/rubrics/suggest/${ticker}${params}`, {});
    },
  });
}
