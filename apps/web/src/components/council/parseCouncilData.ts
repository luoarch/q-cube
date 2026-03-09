
import { VERDICT_LABELS } from './constants';

import type { CouncilData } from './CouncilResultPanel';
import type { AgentOpinion, ChatMessage } from '@q3/shared-contracts';

/**
 * Read a value from an object that may use snake_case or camelCase keys.
 * The AI assistant returns snake_case; the shared contracts use camelCase.
 */
function sc<T>(obj: Record<string, unknown>, camel: string, snake: string): T | undefined {
  return (obj[camel] ?? obj[snake]) as T | undefined;
}

function normalizeOpinion(op: Record<string, unknown>): AgentOpinion {
  return {
    agentId: sc<AgentOpinion['agentId']>(op, 'agentId', 'agent_id') ?? 'greenblatt',
    profileVersion: sc<number>(op, 'profileVersion', 'profile_version') ?? 1,
    promptVersion: sc<number>(op, 'promptVersion', 'prompt_version') ?? 1,
    verdict: (op.verdict as AgentOpinion['verdict']) ?? 'watch',
    confidence: (op.confidence as number) ?? 50,
    dataReliability: sc<AgentOpinion['dataReliability']>(op, 'dataReliability', 'data_reliability') ?? 'medium',
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

/**
 * Parse council data from chat messages.
 * Tries system message JSON first, falls back to agent-message text parsing.
 */
export function parseCouncilData(messages: ChatMessage[]): CouncilData | null {
  // First, try to find a system message with the full council result JSON
  const systemMsg = messages.find((m) => m.role === 'system' && m.content.startsWith('{'));
  if (systemMsg) {
    try {
      const raw = JSON.parse(systemMsg.content) as Record<string, unknown>;
      const rawOpinions = (raw.opinions ?? []) as Record<string, unknown>[];
      const opinions = rawOpinions.map(normalizeOpinion);

      // Scoreboard
      const rawScoreboard = sc<Record<string, unknown>>(raw, 'scoreboard', 'scoreboard');
      const scoreboard = rawScoreboard
        ? {
            entries: ((rawScoreboard.entries ?? []) as Record<string, unknown>[]).map((e) => ({
              agentId: sc<AgentOpinion['agentId']>(e, 'agentId', 'agent_id') ?? 'greenblatt',
              verdict: (e.verdict as AgentOpinion['verdict']) ?? 'watch',
              confidence: (e.confidence as number) ?? 50,
            })),
            consensus: (rawScoreboard.consensus as AgentOpinion['verdict']) ?? null,
            consensusStrength: sc<number>(rawScoreboard, 'consensusStrength', 'consensus_strength') ?? null,
          }
        : {
            entries: opinions.map((o) => ({ agentId: o.agentId, verdict: o.verdict, confidence: o.confidence })),
            consensus: null,
            consensusStrength: null,
          };

      // Conflict matrix
      const rawConflicts = sc<Record<string, unknown>[]>(raw, 'conflictMatrix', 'conflict_matrix') ?? [];
      const conflictMatrix = rawConflicts.map((c) => ({
        agent1: (c.agent1 as AgentOpinion['agentId']) ?? 'greenblatt',
        agent2: (c.agent2 as AgentOpinion['agentId']) ?? 'buffett',
        topic: (c.topic as string) ?? 'verdict',
        agent1Position: sc<string>(c, 'agent1Position', 'agent1_position') ?? '',
        agent2Position: sc<string>(c, 'agent2Position', 'agent2_position') ?? '',
      }));

      // Moderator synthesis
      const rawSynth = sc<Record<string, unknown>>(raw, 'moderatorSynthesis', 'moderator_synthesis');
      const moderatorSynthesis = rawSynth
        ? {
            convergences: (rawSynth.convergences as string[]) ?? [],
            divergences: (rawSynth.divergences as string[]) ?? [],
            biggestRisk: sc<string>(rawSynth, 'biggestRisk', 'biggest_risk') ?? '',
            entryConditions: sc<string[]>(rawSynth, 'entryConditions', 'entry_conditions') ?? [],
            exitConditions: sc<string[]>(rawSynth, 'exitConditions', 'exit_conditions') ?? [],
            overallAssessment: sc<string>(rawSynth, 'overallAssessment', 'overall_assessment') ?? '',
          }
        : undefined;

      // Debate log
      const rawDebate = sc<Record<string, unknown>[]>(raw, 'debateLog', 'debate_log') ?? [];
      const debateLog = rawDebate.map((d) => ({
        roundNumber: sc<number>(d, 'roundNumber', 'round_number') ?? 0,
        agentId: sc<AgentOpinion['agentId']>(d, 'agentId', 'agent_id') ?? 'greenblatt',
        content: (d.content as string) ?? '',
        targetAgentId: sc<AgentOpinion['agentId'] | null>(d, 'targetAgentId', 'target_agent_id') ?? null,
        timestamp: (d.timestamp as string) ?? '',
      }));

      const result: CouncilData = { opinions, scoreboard, conflictMatrix, debateLog };
      if (moderatorSynthesis) result.moderatorSynthesis = moderatorSynthesis;
      return result;
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
      agentId: (m.agentId ?? 'greenblatt') as AgentOpinion['agentId'],
      profileVersion: 1,
      promptVersion: 1,
      verdict: (headerMatch?.[2] ?? 'watch') as AgentOpinion['verdict'],
      confidence: headerMatch ? parseInt(headerMatch[3]!, 10) : 50,
      dataReliability: 'medium' as const,
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
  const conflictMatrix = [];
  for (let i = 0; i < opinions.length; i++) {
    for (let j = i + 1; j < opinions.length; j++) {
      const a = opinions[i]!;
      const b = opinions[j]!;
      if (a.verdict !== b.verdict) {
        conflictMatrix.push({
          agent1: a.agentId,
          agent2: b.agentId,
          topic: 'verdict',
          agent1Position: `${VERDICT_LABELS[a.verdict] ?? a.verdict} (${a.confidence}%)`,
          agent2Position: `${VERDICT_LABELS[b.verdict] ?? b.verdict} (${b.confidence}%)`,
        });
      }
    }
  }

  return { opinions, scoreboard: { entries, consensus: null, consensusStrength: null }, conflictMatrix };
}
