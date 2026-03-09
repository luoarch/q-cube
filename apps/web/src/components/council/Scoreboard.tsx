'use client';

import type { AgentVerdict, CouncilScoreboard } from '@q3/shared-contracts';

import { AGENT_LABELS, VERDICT_COLORS, VERDICT_LABELS } from './constants';
import { VerdictChip } from './VerdictChip';

import styles from './council.module.css';

export function Scoreboard({ scoreboard }: { scoreboard: CouncilScoreboard | undefined }) {
  if (!scoreboard?.entries?.length) return null;
  return (
    <div className={styles.scoreboard}>
      <div className={styles.scoreboardTitle}>Placar do Conselho</div>
      <div className={styles.scoreboardEntries}>
        {scoreboard.entries.map((e) => (
          <div key={e.agentId} className={styles.scoreboardEntry}>
            <span className={styles.scoreboardAgentLabel}>
              {AGENT_LABELS[e.agentId] ?? e.agentId}
            </span>
            <VerdictChip verdict={e.verdict} confidence={e.confidence} />
          </div>
        ))}
      </div>
      {scoreboard.consensus && (
        <div className={styles.scoreboardConsensus}>
          Consenso:{' '}
          <strong style={{ color: VERDICT_COLORS[scoreboard.consensus as AgentVerdict] ?? '#94a3b8' }}>
            {VERDICT_LABELS[scoreboard.consensus as AgentVerdict] ?? scoreboard.consensus}
          </strong>
          {scoreboard.consensusStrength != null && (
            <span> ({Math.round(scoreboard.consensusStrength * 100)}% dos agentes)</span>
          )}
        </div>
      )}
    </div>
  );
}
