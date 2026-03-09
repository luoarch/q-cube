'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  useArchiveSession,
  useChatMessages,
  useChatSessions,
  useCreateChatSession,
  useSendMessage,
} from '../../../src/hooks/api/useChat';
import {
  CouncilResultPanel,
  DISCLAIMER,
  MODE_LABELS,
  parseCouncilData,
} from '../../../src/components/council';

import type { ChatMessage, ChatMode } from '@q3/shared-contracts';

import styles from './chat.module.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);

  if (diffSec < 60) return 'agora';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}min`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h`;
  return new Date(dateStr).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';

  // Don't render agent messages (shown in council panel) or system messages (raw JSON)
  if (msg.role === 'agent' || msg.role === 'system') return null;

  return (
    <div className={isUser ? styles.messageBubbleRight : styles.messageBubbleLeft}>
      <div className={isUser ? styles.messageUser : styles.messageAssistant}>
        <div className={styles.messageContent}>{msg.content}</div>
        <div className={styles.messageTime}>
          {msg.modelUsed && <>{msg.modelUsed} · </>}
          {formatRelativeTime(msg.createdAt)}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Typing indicator
// ---------------------------------------------------------------------------

function TypingIndicator() {
  return (
    <div className={styles.typingIndicator}>
      <div className={styles.typingBubble}>
        <span className={styles.typingDot} />
        <span className={styles.typingDot} />
        <span className={styles.typingDot} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading skeletons
// ---------------------------------------------------------------------------

function SessionListSkeleton() {
  return (
    <>
      {[1, 2, 3].map((i) => (
        <div key={i} className={`${styles.sessionSkeleton} ${styles.skeletonPulse}`} />
      ))}
    </>
  );
}

function MessagesSkeleton() {
  return (
    <>
      <div className={`${styles.messageSkeletonMedium} ${styles.skeletonPulse}`} />
      <div className={`${styles.messageSkeletonShort} ${styles.messageSkeletonRight} ${styles.skeletonPulse}`} />
      <div className={`${styles.messageSkeletonLong} ${styles.skeletonPulse}`} />
      <div className={`${styles.messageSkeletonShort} ${styles.messageSkeletonRight} ${styles.skeletonPulse}`} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Chat panel with council-aware rendering
// ---------------------------------------------------------------------------

function ChatPanel({
  sessionId,
  sessionMode,
  initialTicker = '',
}: {
  sessionId: string;
  sessionMode: ChatMode;
  initialTicker?: string;
}) {
  const { data: messages } = useChatMessages(sessionId);
  const sendMutation = useSendMessage(sessionId);
  const [input, setInput] = useState('');
  const [tickers, setTickers] = useState(initialTicker);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const needsTickers = sessionMode !== 'free_chat';

  const handleSend = useCallback(() => {
    const content = input.trim();
    if (!content || sendMutation.isPending) return;
    setInput('');

    const tickerList = tickers
      .split(/[,;\s]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);

    sendMutation.mutate({
      content,
      mode: sessionMode !== 'free_chat' ? sessionMode : undefined,
      tickers: tickerList.length > 0 ? tickerList : undefined,
    });
  }, [input, tickers, sessionMode, sendMutation]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const councilData = messages ? parseCouncilData(messages) : null;

  return (
    <div className={styles.chatPanel}>
      {/* Messages */}
      <div className={styles.messagesArea}>
        {councilData && <CouncilResultPanel data={councilData} />}
        {!messages ? (
          <MessagesSkeleton />
        ) : (
          messages.map((m) => <MessageBubble key={m.id} msg={m} />)
        )}
        {sendMutation.isPending && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Disclaimer */}
      <div className={styles.disclaimer}>{DISCLAIMER}</div>

      {/* Input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className={styles.inputForm}
      >
        {needsTickers && (
          <div className={styles.tickerInputRow}>
            <label htmlFor="ticker-input" className={styles.srOnly}>Tickers</label>
            <input
              id="ticker-input"
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              placeholder="Tickers (ex: WEGE3, BBAS3, ITUB4)"
              className={styles.tickerInput}
            />
          </div>
        )}

        <div className={styles.inputRow}>
          <label htmlFor="message-input" className={styles.srOnly}>Mensagem</label>
          <input
            id="message-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              needsTickers
                ? 'Descreva o que deseja analisar...'
                : 'Pergunte sobre uma empresa ou estrategia...'
            }
            className={styles.messageInput}
          />
          <button
            type="submit"
            disabled={sendMutation.isPending || !input.trim()}
            className={styles.sendButton}
          >
            {sendMutation.isPending ? '...' : 'Enviar'}
          </button>
        </div>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page (uses useSearchParams — must be inside Suspense)
// ---------------------------------------------------------------------------

export function ChatPageInner() {
  const searchParams = useSearchParams();
  const tickerParam = searchParams.get('ticker');

  const { data: sessions } = useChatSessions();
  const createSession = useCreateChatSession();
  const archiveSession = useArchiveSession();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [selectedMode, setSelectedMode] = useState<ChatMode>(tickerParam ? 'roundtable' : 'free_chat');
  const [initialTicker] = useState(tickerParam ?? '');

  const activeSession = sessions?.find((s) => s.id === activeSessionId);
  const activeMode = activeSession?.mode ?? selectedMode;

  const handleNewSession = useCallback(() => {
    createSession.mutate(
      { mode: selectedMode },
      { onSuccess: (session) => setActiveSessionId(session.id) },
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

      <div className={styles.layout}>
        {/* Sidebar */}
        <aside className={styles.sidebar} aria-label="Sessoes de chat">
          <div className={styles.sidebarControls}>
            <label htmlFor="mode-select" className={styles.srOnly}>Modo</label>
            <select
              id="mode-select"
              value={selectedMode}
              onChange={(e) => setSelectedMode(e.target.value as ChatMode)}
              className={styles.modeSelect}
            >
              {Object.entries(MODE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <button
              onClick={handleNewSession}
              disabled={createSession.isPending}
              className={styles.newSessionButton}
            >
              + Nova
            </button>
          </div>

          {!sessions ? (
            <SessionListSkeleton />
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                className={`${styles.sessionButton} ${s.id === activeSessionId ? styles.sessionButtonActive : ''}`}
                onClick={() => setActiveSessionId(s.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') setActiveSessionId(s.id); }}
              >
                <div className={styles.sessionRow}>
                  <div className={styles.sessionInfo}>
                    <div className={styles.sessionTitle}>{s.title ?? MODE_LABELS[s.mode]}</div>
                    <div className={styles.sessionDate}>
                      {new Date(s.createdAt).toLocaleDateString('pt-BR')}
                    </div>
                  </div>
                  <button
                    className={styles.archiveButton}
                    title="Arquivar sessao"
                    aria-label="Arquivar sessao"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (activeSessionId === s.id) setActiveSessionId(null);
                      archiveSession.mutate(s.id);
                    }}
                  >
                    ×
                  </button>
                </div>
              </div>
            ))
          )}
        </aside>

        {/* Main panel */}
        <main className={styles.mainPanel}>
          {activeSessionId ? (
            <ChatPanel sessionId={activeSessionId} sessionMode={activeMode} initialTicker={initialTicker} />
          ) : (
            <div className={styles.emptyState}>
              Selecione ou crie uma sessao para comecar.
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
