import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { UpdateUserContext, UserContextProfile } from '@q3/shared-contracts';

export function useUserContext() {
  return useQuery<UserContextProfile>({
    queryKey: ['user-context'],
    queryFn: () => apiClient.get<UserContextProfile>('/user-context'),
  });
}

export function useUpdateUserContext() {
  const qc = useQueryClient();
  return useMutation<UserContextProfile, Error, UpdateUserContext>({
    mutationFn: (input) => apiClient.put<UserContextProfile>('/user-context', input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['user-context'] }),
  });
}
