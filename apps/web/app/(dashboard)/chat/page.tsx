'use client';

import Link from 'next/link';
import { useCallback, useRef, useState } from 'react';

import {
  useChatMessages,
  useChatSessions,
  useCreateChatSession,
  useSendMessage,
} from '../../../src/hooks/api/useChat';

import type { ChatMessage, ChatMode } from '@q3/shared-contracts';

const MODE_LABELS: Record<ChatMode, string> = {
  free_chat: 'Chat Livre',
  agent_solo: 'Agente Solo',
  roundtable: 'Mesa Redonda',
  debate: 'Debate',
  comparison: 'Comparacao',
};

const DISCLAIMER =
  'Este conteudo e meramente educacional e analitico, nao constituindo recomendacao de investimento personalizada.';

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 8,
      }}
    >
      <div
        style={{
          maxWidth: '75%',
          padding: '0.5rem 0.75rem',
          borderRadius: 8,
          background: isUser ? 'rgba(251,191,36,0.15)' : 'rgba(148,163,184,0.08)',
          color: 'var(--text-primary, #e2e8f0)',
          fontSize: 14,
        }}
      >
        {msg.agentId && (
          <div style={{ fontSize: 11, color: 'var(--accent-gold, #fbbf24)', marginBottom: 4, fontWeight: 600 }}>
            {msg.agentId}
          </div>
        )}
        <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
        {msg.modelUsed && (
          <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
            {msg.modelUsed}
          </div>
        )}
      </div>
    </div>
  );
}

function ChatPanel({ sessionId }: { sessionId: string }) {
  const { data: messages } = useChatMessages(sessionId);
  const sendMutation = useSendMessage(sessionId);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleSend = useCallback(() => {
    const content = input.trim();
    if (!content || sendMutation.isPending) return;
    setInput('');
    sendMutation.mutate({ content });
  }, [input, sendMutation]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
        {messages?.map((m) => <MessageBubble key={m.id} msg={m} />)}
        <div ref={messagesEndRef} />
      </div>

      {/* Disclaimer */}
      <div style={{ padding: '0 1rem', fontSize: 10, color: 'var(--text-secondary)' }}>
        {DISCLAIMER}
      </div>

      {/* Input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        style={{ display: 'flex', gap: 8, padding: '0.75rem 1rem' }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pergunte sobre uma empresa ou estrategia..."
          style={{
            flex: 1,
            padding: '0.5rem 0.75rem',
            background: 'rgba(148,163,184,0.08)',
            border: '1px solid rgba(148,163,184,0.2)',
            borderRadius: 6,
            color: 'var(--text-primary, #e2e8f0)',
            fontSize: 14,
          }}
        />
        <button
          type="submit"
          disabled={sendMutation.isPending || !input.trim()}
          style={{
            padding: '0.5rem 1rem',
            background: 'var(--accent-gold, #fbbf24)',
            color: '#0a0e1a',
            border: 'none',
            borderRadius: 6,
            fontWeight: 600,
            cursor: 'pointer',
            opacity: sendMutation.isPending ? 0.6 : 1,
          }}
        >
          {sendMutation.isPending ? '...' : 'Enviar'}
        </button>
      </form>
    </div>
  );
}

export default function ChatPage() {
  const { data: sessions } = useChatSessions();
  const createSession = useCreateChatSession();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [selectedMode, setSelectedMode] = useState<ChatMode>('free_chat');

  const handleNewSession = useCallback(() => {
    createSession.mutate(
      { mode: selectedMode },
      {
        onSuccess: (session) => setActiveSessionId(session.id),
      },
    );
  }, [createSession, selectedMode]);

  return (
    <div className="dashboard-page" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <header className="dashboard-header">
        <Link href="/ranking" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
          ← Ranking
        </Link>
        <h1>AI Council</h1>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar — sessions list */}
        <div
          style={{
            width: 240,
            borderRight: '1px solid rgba(148,163,184,0.15)',
            padding: '1rem',
            overflowY: 'auto',
          }}
        >
          <div style={{ display: 'flex', gap: 4, marginBottom: 12, flexWrap: 'wrap' }}>
            <select
              value={selectedMode}
              onChange={(e) => setSelectedMode(e.target.value as ChatMode)}
              style={{
                flex: 1,
                fontSize: 12,
                padding: '4px 6px',
                background: 'rgba(148,163,184,0.08)',
                border: '1px solid rgba(148,163,184,0.2)',
                borderRadius: 4,
                color: 'var(--text-primary, #e2e8f0)',
              }}
            >
              {Object.entries(MODE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <button
              onClick={handleNewSession}
              disabled={createSession.isPending}
              style={{
                fontSize: 12,
                padding: '4px 8px',
                background: 'var(--accent-gold, #fbbf24)',
                color: '#0a0e1a',
                border: 'none',
                borderRadius: 4,
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              + Nova
            </button>
          </div>

          {sessions?.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveSessionId(s.id)}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                padding: '0.5rem',
                marginBottom: 4,
                background:
                  s.id === activeSessionId ? 'rgba(251,191,36,0.1)' : 'transparent',
                border:
                  s.id === activeSessionId
                    ? '1px solid rgba(251,191,36,0.3)'
                    : '1px solid transparent',
                borderRadius: 6,
                color: 'var(--text-primary, #e2e8f0)',
                cursor: 'pointer',
                fontSize: 13,
              }}
            >
              <div style={{ fontWeight: 500 }}>{s.title ?? MODE_LABELS[s.mode]}</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                {new Date(s.createdAt).toLocaleDateString('pt-BR')}
              </div>
            </button>
          ))}
        </div>

        {/* Main panel */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {activeSessionId ? (
            <ChatPanel sessionId={activeSessionId} />
          ) : (
            <div
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--text-secondary)',
                fontSize: 14,
              }}
            >
              Selecione ou crie uma sessao para comecar.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
