import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiClient } from './apiClient';

import type { ChatMessage, ChatSession, CreateChatSession, SendMessage } from '@q3/shared-contracts';

export function useChatSessions() {
  return useQuery<ChatSession[]>({
    queryKey: ['chat-sessions'],
    queryFn: () => apiClient.get<ChatSession[]>('/chat/sessions'),
  });
}

export function useChatMessages(sessionId: string | null) {
  return useQuery<ChatMessage[]>({
    queryKey: ['chat-messages', sessionId],
    queryFn: () => apiClient.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),
    enabled: !!sessionId,
  });
}

export function useCreateChatSession() {
  const qc = useQueryClient();
  return useMutation<ChatSession, Error, CreateChatSession>({
    mutationFn: (input) => apiClient.post<ChatSession>('/chat/sessions', input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['chat-sessions'] }),
  });
}

export function useSendMessage(sessionId: string) {
  const qc = useQueryClient();
  return useMutation<ChatMessage, Error, SendMessage>({
    mutationFn: (input) => apiClient.post<ChatMessage>(`/chat/sessions/${sessionId}/messages`, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['chat-messages', sessionId] }),
  });
}

export function useArchiveSession() {
  const qc = useQueryClient();
  return useMutation<ChatSession, Error, string>({
    mutationFn: (sessionId) => apiClient.patch<ChatSession>(`/chat/sessions/${sessionId}/archive`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['chat-sessions'] }),
  });
}
