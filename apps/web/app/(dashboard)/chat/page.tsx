'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

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

const VERDICT_COLORS: Record<string, string> = {
  buy: '#22c55e',
  watch: '#fbbf24',
  avoid: '#ef4444',
  insufficient_data: '#94a3b8',
};

const VERDICT_LABELS: Record<string, string> = {
  buy: 'Comprar',
  watch: 'Observar',
  avoid: 'Evitar',
  insufficient_data: 'Dados Insuficientes',
};

const AGENT_LABELS: Record<string, string> = {
  barsi: 'Barsi-inspired',
  graham: 'Graham-inspired',
  greenblatt: 'Greenblatt-inspired',
  buffett: 'Buffett-inspired',
  moderator: 'Moderador Q³',
};

const DISCLAIMER =
  'Este conteudo e meramente educacional e analitico, nao constituindo recomendacao de investimento personalizada.';

// ---------------------------------------------------------------------------
// Council result types (inline — matches shared-contracts)
// ---------------------------------------------------------------------------

type AgentOpinion = {
  agentId: string;
  verdict: string;
  confidence: number;
  dataReliability?: string;
  thesis: string;
  reasonsFor: string[];
  reasonsAgainst: string[];
  keyMetricsUsed: string[];
  hardRejectsTriggered: string[];
  unknowns: string[];
  whatWouldChangeMyMind: string[];
  investorFit: string[];
};

type ScoreboardEntry = {
  agentId: string;
  verdict: string;
  confidence: number;
};

type ConflictEntry = {
  agent1: string;
  agent2: string;
  topic: string;
  agent1Position: string;
  agent2Position: string;
};

type DebateRoundEntry = {
  roundNumber: number;
  agentId: string;
  content: string;
  targetAgentId: string | null;
};

type CouncilData = {
  opinions?: AgentOpinion[];
  scoreboard?: { entries: ScoreboardEntry[]; consensus: string | null; consensusStrength: number | null };
  conflictMatrix?: ConflictEntry[];
  moderatorSynthesis?: {
    convergences: string[];
    divergences: string[];
    biggestRisk: string;
    entryConditions: string[];
    exitConditions: string[];
    overallAssessment: string;
  };
  debateLog?: DebateRoundEntry[];
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function VerdictChip({ verdict, confidence }: { verdict: string; confidence: number }) {
  const color = VERDICT_COLORS[verdict] ?? '#94a3b8';
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 8px',
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 600,
        background: `${color}22`,
        color,
        border: `1px solid ${color}44`,
      }}
    >
      {VERDICT_LABELS[verdict] ?? verdict}
      <span style={{ fontSize: 10, opacity: 0.8 }}>{confidence}%</span>
    </span>
  );
}

function Scoreboard({ scoreboard }: { scoreboard: CouncilData['scoreboard'] }) {
  if (!scoreboard?.entries?.length) return null;
  return (
    <div
      style={{
        padding: '0.75rem',
        background: 'rgba(148,163,184,0.05)',
        borderRadius: 8,
        marginBottom: 12,
        border: '1px solid rgba(148,163,184,0.12)',
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--accent-gold, #fbbf24)' }}>
        Placar do Conselho
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {scoreboard.entries.map((e) => (
          <div key={e.agentId} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              {AGENT_LABELS[e.agentId] ?? e.agentId}
            </span>
            <VerdictChip verdict={e.verdict} confidence={e.confidence} />
          </div>
        ))}
      </div>
      {scoreboard.consensus && (
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-secondary)' }}>
          Consenso: <strong style={{ color: VERDICT_COLORS[scoreboard.consensus] ?? '#94a3b8' }}>
            {VERDICT_LABELS[scoreboard.consensus] ?? scoreboard.consensus}
          </strong>
          {scoreboard.consensusStrength != null && (
            <span> ({Math.round(scoreboard.consensusStrength * 100)}% dos agentes)</span>
          )}
        </div>
      )}
    </div>
  );
}

function AgentCard({ opinion, defaultExpanded }: { opinion: AgentOpinion; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded ?? false);
  const color = VERDICT_COLORS[opinion.verdict] ?? '#94a3b8';

  return (
    <div
      style={{
        marginBottom: 8,
        borderRadius: 8,
        border: `1px solid ${color}33`,
        background: 'rgba(148,163,184,0.04)',
        overflow: 'hidden',
      }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.6rem 0.75rem',
          background: 'transparent',
          border: 'none',
          color: 'var(--text-primary, #e2e8f0)',
          cursor: 'pointer',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>
            {AGENT_LABELS[opinion.agentId] ?? opinion.agentId}
          </span>
          <VerdictChip verdict={opinion.verdict} confidence={opinion.confidence} />
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div style={{ padding: '0 0.75rem 0.75rem', fontSize: 13 }}>
          {/* Thesis */}
          <div style={{ marginBottom: 8, lineHeight: 1.5 }}>{opinion.thesis}</div>

          {/* Reasons For */}
          {opinion.reasonsFor?.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#22c55e', marginBottom: 2 }}>A Favor</div>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {opinion.reasonsFor.map((r, i) => (
                  <li key={i} style={{ fontSize: 12, marginBottom: 2 }}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Reasons Against */}
          {opinion.reasonsAgainst?.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#ef4444', marginBottom: 2 }}>Contra</div>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {opinion.reasonsAgainst.map((r, i) => (
                  <li key={i} style={{ fontSize: 12, marginBottom: 2 }}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Key Metrics */}
          {opinion.keyMetricsUsed?.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 2 }}>
                Metricas Utilizadas
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {opinion.keyMetricsUsed.map((m) => (
                  <span
                    key={m}
                    style={{
                      fontSize: 10,
                      padding: '1px 6px',
                      borderRadius: 4,
                      background: 'rgba(148,163,184,0.1)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {m}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Hard Rejects */}
          {opinion.hardRejectsTriggered?.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#ef4444', marginBottom: 2 }}>
                Rejeicoes Automaticas
              </div>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {opinion.hardRejectsTriggered.map((r, i) => (
                  <li key={i} style={{ fontSize: 12, color: '#ef4444', marginBottom: 2 }}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* What Would Change My Mind */}
          {opinion.whatWouldChangeMyMind?.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-gold, #fbbf24)', marginBottom: 2 }}>
                O que mudaria minha opiniao
              </div>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {opinion.whatWouldChangeMyMind.map((r, i) => (
                  <li key={i} style={{ fontSize: 12, marginBottom: 2 }}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Unknowns */}
          {opinion.unknowns?.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 2 }}>
                Incertezas
              </div>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {opinion.unknowns.map((r, i) => (
                  <li key={i} style={{ fontSize: 12, marginBottom: 2 }}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Investor Fit */}
          {opinion.investorFit?.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 2 }}>
                Perfil do Investidor
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {opinion.investorFit.map((f) => (
                  <span
                    key={f}
                    style={{
                      fontSize: 10,
                      padding: '1px 6px',
                      borderRadius: 4,
                      background: 'rgba(251,191,36,0.1)',
                      color: 'var(--accent-gold, #fbbf24)',
                    }}
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ConflictMatrix({ conflicts }: { conflicts: ConflictEntry[] }) {
  if (!conflicts?.length) return null;
  return (
    <div
      style={{
        padding: '0.75rem',
        background: 'rgba(239,68,68,0.04)',
        borderRadius: 8,
        marginBottom: 12,
        border: '1px solid rgba(239,68,68,0.15)',
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: '#ef4444' }}>
        Divergencias
      </div>
      {conflicts.map((c, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 8,
            marginBottom: i < conflicts.length - 1 ? 8 : 0,
            fontSize: 12,
          }}
        >
          <span style={{ fontWeight: 600, minWidth: 80 }}>
            {AGENT_LABELS[c.agent1] ?? c.agent1}
          </span>
          <span style={{ color: 'var(--text-secondary)' }}>vs</span>
          <span style={{ fontWeight: 600, minWidth: 80 }}>
            {AGENT_LABELS[c.agent2] ?? c.agent2}
          </span>
          <span style={{ color: 'var(--text-secondary)', flex: 1 }}>
            {c.agent1Position} | {c.agent2Position}
          </span>
        </div>
      ))}
    </div>
  );
}

function DebateTimeline({ rounds }: { rounds: DebateRoundEntry[] }) {
  if (!rounds?.length) return null;

  const roundGroups = [1, 2, 3, 4].map((num) => ({
    number: num,
    label: ['Veredicto Inicial', 'Contestacao', 'Replica', 'Sintese do Moderador'][num - 1]!,
    entries: rounds.filter((r) => r.roundNumber === num),
  }));

  return (
    <div
      style={{
        padding: '0.75rem',
        background: 'rgba(148,163,184,0.04)',
        borderRadius: 8,
        marginBottom: 12,
        border: '1px solid rgba(148,163,184,0.12)',
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--accent-gold, #fbbf24)' }}>
        Timeline do Debate
      </div>
      {roundGroups
        .filter((g) => g.entries.length > 0)
        .map((group) => (
          <div key={group.number} style={{ marginBottom: 10 }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--text-secondary)',
                marginBottom: 4,
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
              }}
            >
              Round {group.number} — {group.label}
            </div>
            {group.entries.map((entry, i) => (
              <div
                key={i}
                style={{
                  marginLeft: 12,
                  paddingLeft: 12,
                  borderLeft: '2px solid rgba(148,163,184,0.2)',
                  marginBottom: 6,
                  fontSize: 12,
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 11, color: 'var(--accent-gold, #fbbf24)' }}>
                  {AGENT_LABELS[entry.agentId] ?? entry.agentId}
                  {entry.targetAgentId && (
                    <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}>
                      {' → '}{AGENT_LABELS[entry.targetAgentId] ?? entry.targetAgentId}
                    </span>
                  )}
                </div>
                <div style={{ color: 'var(--text-primary, #e2e8f0)', lineHeight: 1.4 }}>
                  {entry.content}
                </div>
              </div>
            ))}
          </div>
        ))}
    </div>
  );
}

function CouncilResultPanel({ data }: { data: CouncilData }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <Scoreboard scoreboard={data.scoreboard} />
      <ConflictMatrix conflicts={data.conflictMatrix ?? []} />
      <DebateTimeline rounds={data.debateLog ?? []} />

      {/* Moderator Synthesis */}
      {data.moderatorSynthesis?.overallAssessment && (
        <div
          style={{
            padding: '0.75rem',
            background: 'rgba(251,191,36,0.05)',
            borderRadius: 8,
            marginBottom: 12,
            border: '1px solid rgba(251,191,36,0.15)',
          }}
        >
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: 'var(--accent-gold, #fbbf24)' }}>
            Sintese do Moderador
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}>
            {data.moderatorSynthesis.overallAssessment}
          </div>

          {data.moderatorSynthesis.convergences?.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#22c55e', marginBottom: 2 }}>Convergencias</div>
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12 }}>
                {data.moderatorSynthesis.convergences.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}

          {data.moderatorSynthesis.biggestRisk && (
            <div style={{ marginTop: 6, fontSize: 12, color: '#ef4444' }}>
              Maior Risco: {data.moderatorSynthesis.biggestRisk}
            </div>
          )}
        </div>
      )}

      {/* Agent Opinion Cards */}
      {data.opinions
        ?.filter((o) => o.agentId !== 'moderator')
        .map((opinion) => (
          <AgentCard key={opinion.agentId} opinion={opinion} />
        ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Parse council data from assistant messages
// ---------------------------------------------------------------------------

// Helper to get a value from an object that may use snake_case or camelCase keys
function sc<T>(obj: Record<string, unknown>, camel: string, snake: string): T | undefined {
  return (obj[camel] ?? obj[snake]) as T | undefined;
}

function normalizeOpinion(op: Record<string, unknown>): AgentOpinion {
  return {
    agentId: sc<string>(op, 'agentId', 'agent_id') ?? 'unknown',
    verdict: (op.verdict as string) ?? 'watch',
    confidence: (op.confidence as number) ?? 50,
    dataReliability: sc<string>(op, 'dataReliability', 'data_reliability'),
    thesis: (op.thesis as string) ?? '',
    reasonsFor: sc<string[]>(op, 'reasonsFor', 'reasons_for') ?? [],
    reasonsAgainst: sc<string[]>(op, 'reasonsAgainst', 'reasons_against') ?? [],
    keyMetricsUsed: sc<string[]>(op, 'keyMetricsUsed', 'key_metrics_used') ?? [],
    hardRejectsTriggered: sc<string[]>(op, 'hardRejectsTriggered', 'hard_rejects_triggered') ?? [],
    unknowns: (op.unknowns as string[]) ?? [],
    whatWouldChangeMyMind: sc<string[]>(op, 'whatWouldChangeMyMind', 'what_would_change_my_mind') ?? [],
    investorFit: sc<string[]>(op, 'investorFit', 'investor_fit') ?? [],
  };
}

function tryParseCouncilData(messages: ChatMessage[]): CouncilData | null {
  // First, try to find a system message with the full council result JSON
  const systemMsg = messages.find((m) => m.role === 'system' && m.content.startsWith('{'));
  if (systemMsg) {
    try {
      const raw = JSON.parse(systemMsg.content) as Record<string, unknown>;
      const rawOpinions = (raw.opinions ?? []) as Record<string, unknown>[];
      const opinions = rawOpinions.map(normalizeOpinion);

      // Scoreboard — from response or build from opinions
      const rawScoreboard = (sc<Record<string, unknown>>(raw, 'scoreboard', 'scoreboard'));
      const scoreboard = rawScoreboard ? {
        entries: ((rawScoreboard.entries ?? []) as Record<string, unknown>[]).map((e) => ({
          agentId: sc<string>(e, 'agentId', 'agent_id') ?? '',
          verdict: (e.verdict as string) ?? 'watch',
          confidence: (e.confidence as number) ?? 50,
        })),
        consensus: (rawScoreboard.consensus as string) ?? null,
        consensusStrength: sc<number>(rawScoreboard, 'consensusStrength', 'consensus_strength') ?? null,
      } : {
        entries: opinions.map((o) => ({ agentId: o.agentId, verdict: o.verdict, confidence: o.confidence })),
        consensus: null,
        consensusStrength: null,
      };

      // Conflict matrix
      const rawConflicts = sc<Record<string, unknown>[]>(raw, 'conflictMatrix', 'conflict_matrix') ?? [];
      const conflictMatrix = rawConflicts.map((c) => ({
        agent1: (c.agent1 as string) ?? '',
        agent2: (c.agent2 as string) ?? '',
        topic: (c.topic as string) ?? 'verdict',
        agent1Position: sc<string>(c, 'agent1Position', 'agent1_position') ?? '',
        agent2Position: sc<string>(c, 'agent2Position', 'agent2_position') ?? '',
      }));

      // Moderator synthesis
      const rawSynth = sc<Record<string, unknown>>(raw, 'moderatorSynthesis', 'moderator_synthesis');
      const moderatorSynthesis = rawSynth ? {
        convergences: (rawSynth.convergences as string[]) ?? [],
        divergences: (rawSynth.divergences as string[]) ?? [],
        biggestRisk: sc<string>(rawSynth, 'biggestRisk', 'biggest_risk') ?? '',
        entryConditions: sc<string[]>(rawSynth, 'entryConditions', 'entry_conditions') ?? [],
        exitConditions: sc<string[]>(rawSynth, 'exitConditions', 'exit_conditions') ?? [],
        overallAssessment: sc<string>(rawSynth, 'overallAssessment', 'overall_assessment') ?? '',
      } : undefined;

      // Debate log
      const rawDebate = sc<Record<string, unknown>[]>(raw, 'debateLog', 'debate_log') ?? [];
      const debateLog = rawDebate.map((d) => ({
        roundNumber: sc<number>(d, 'roundNumber', 'round_number') ?? 0,
        agentId: sc<string>(d, 'agentId', 'agent_id') ?? '',
        content: (d.content as string) ?? '',
        targetAgentId: sc<string>(d, 'targetAgentId', 'target_agent_id') ?? null,
      }));

      return { opinions, scoreboard, conflictMatrix, moderatorSynthesis, debateLog };
    } catch {
      // Fall through to agent-message parsing
    }
  }

  // Fallback: reconstruct from agent-role messages
  const agentMessages = messages.filter((m) => m.role === 'agent' && m.agentId);
  if (agentMessages.length === 0) return null;

  const opinions: AgentOpinion[] = agentMessages.map((m) => {
    const lines = m.content.split('\n');
    const headerMatch = lines[0]?.match(/\*\*(.+?)\*\*\s*—\s*(\w+)\s*\(confianca:\s*(\d+)%\)/);
    return {
      agentId: m.agentId ?? 'unknown',
      verdict: headerMatch?.[2] ?? 'watch',
      confidence: headerMatch ? parseInt(headerMatch[3]!, 10) : 50,
      thesis: lines.slice(2).join('\n').trim() || m.content,
      reasonsFor: [],
      reasonsAgainst: [],
      keyMetricsUsed: [],
      hardRejectsTriggered: [],
      unknowns: [],
      whatWouldChangeMyMind: [],
      investorFit: [],
    };
  });

  const entries = opinions.map((o) => ({ agentId: o.agentId, verdict: o.verdict, confidence: o.confidence }));
  const conflicts: ConflictEntry[] = [];
  for (let i = 0; i < opinions.length; i++) {
    for (let j = i + 1; j < opinions.length; j++) {
      const a = opinions[i]!;
      const b = opinions[j]!;
      if (a.verdict !== b.verdict) {
        conflicts.push({
          agent1: a.agentId, agent2: b.agentId, topic: 'verdict',
          agent1Position: `${VERDICT_LABELS[a.verdict] ?? a.verdict} (${a.confidence}%)`,
          agent2Position: `${VERDICT_LABELS[b.verdict] ?? b.verdict} (${b.confidence}%)`,
        });
      }
    }
  }

  return { opinions, scoreboard: { entries, consensus: null, consensusStrength: null }, conflictMatrix: conflicts };
}

// ---------------------------------------------------------------------------
// Message display
// ---------------------------------------------------------------------------

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  const isAgent = msg.role === 'agent';
  const isSystem = msg.role === 'system';

  // Don't render agent messages (shown in council panel) or system messages (raw JSON)
  if (isAgent || isSystem) return null;

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

// ---------------------------------------------------------------------------
// ChatPanel with council-aware rendering
// ---------------------------------------------------------------------------

function ChatPanel({ sessionId, sessionMode, initialTicker = '' }: { sessionId: string; sessionMode: ChatMode; initialTicker?: string }) {
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

  // Build council data from agent messages
  const councilData = messages ? tryParseCouncilData(messages) : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
        {/* Council result panel (scoreboard + agents + conflicts) */}
        {councilData && <CouncilResultPanel data={councilData} />}

        {/* Regular messages */}
        {messages?.map((m) => <MessageBubble key={m.id} msg={m} />)}
        <div ref={messagesEndRef} />
      </div>

      {/* Disclaimer */}
      <div style={{ padding: '0 1rem', fontSize: 10, color: 'var(--text-secondary)' }}>
        {DISCLAIMER}
      </div>

      {/* Input area */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        style={{ padding: '0.75rem 1rem' }}
      >
        {/* Ticker input for council modes */}
        {needsTickers && (
          <div style={{ marginBottom: 6 }}>
            <input
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              placeholder="Tickers (ex: WEGE3, BBAS3, ITUB4)"
              style={{
                width: '100%',
                padding: '0.4rem 0.75rem',
                background: 'rgba(148,163,184,0.08)',
                border: '1px solid rgba(148,163,184,0.2)',
                borderRadius: 6,
                color: 'var(--accent-gold, #fbbf24)',
                fontSize: 13,
              }}
            />
          </div>
        )}

        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              needsTickers
                ? 'Descreva o que deseja analisar...'
                : 'Pergunte sobre uma empresa ou estrategia...'
            }
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
        </div>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ChatPage() {
  const searchParams = useSearchParams();
  const tickerParam = searchParams.get('ticker');

  const { data: sessions } = useChatSessions();
  const createSession = useCreateChatSession();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [selectedMode, setSelectedMode] = useState<ChatMode>(tickerParam ? 'roundtable' : 'free_chat');
  const [initialTicker] = useState(tickerParam ?? '');

  const activeSession = sessions?.find((s) => s.id === activeSessionId);
  const activeMode = activeSession?.mode ?? selectedMode;

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
            <ChatPanel sessionId={activeSessionId} sessionMode={activeMode} initialTicker={initialTicker} />
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
