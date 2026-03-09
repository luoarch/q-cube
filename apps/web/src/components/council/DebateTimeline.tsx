'use client';


import { AGENT_LABELS } from './constants';
import styles from './council.module.css';

import type { DebateRound } from '@q3/shared-contracts';

const ROUND_LABELS = [
  'Veredicto Inicial',
  'Contestacao',
  'Replica',
  'Sintese do Moderador',
] as const;

export function DebateTimeline({ rounds }: { rounds: DebateRound[] }) {
  if (!rounds?.length) return null;

  const roundGroups = [1, 2, 3, 4].map((num) => ({
    number: num,
    label: ROUND_LABELS[num - 1]!,
    entries: rounds.filter((r) => r.roundNumber === num),
  }));

  return (
    <div className={styles.debatePanel}>
      <div className={styles.debateTitle}>Timeline do Debate</div>
      {roundGroups
        .filter((g) => g.entries.length > 0)
        .map((group) => (
          <div key={group.number} className={styles.debateRound}>
            <div className={styles.debateRoundLabel}>
              Round {group.number} — {group.label}
            </div>
            {group.entries.map((entry, i) => (
              <div key={i} className={styles.debateEntry}>
                <div className={styles.debateEntryAgent}>
                  {AGENT_LABELS[entry.agentId] ?? entry.agentId}
                  {entry.targetAgentId && (
                    <span className={styles.debateEntryTarget}>
                      {' \u2192 '}{AGENT_LABELS[entry.targetAgentId] ?? entry.targetAgentId}
                    </span>
                  )}
                </div>
                <div className={styles.debateEntryContent}>{entry.content}</div>
              </div>
            ))}
          </div>
        ))}
    </div>
  );
}
