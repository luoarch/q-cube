'use client';


import { AGENT_LABELS } from './constants';
import styles from './council.module.css';

import type { ConflictEntry } from '@q3/shared-contracts';

export function ConflictMatrix({ conflicts }: { conflicts: ConflictEntry[] }) {
  if (!conflicts?.length) return null;
  return (
    <div className={styles.conflictPanel}>
      <div className={styles.conflictTitle}>Divergencias</div>
      {conflicts.map((c, i) => (
        <div key={i} className={styles.conflictRow}>
          <span className={styles.conflictAgent}>
            {AGENT_LABELS[c.agent1] ?? c.agent1}
          </span>
          <span className={styles.conflictVs}>vs</span>
          <span className={styles.conflictAgent}>
            {AGENT_LABELS[c.agent2] ?? c.agent2}
          </span>
          <span className={styles.conflictPosition}>
            {c.agent1Position} | {c.agent2Position}
          </span>
        </div>
      ))}
    </div>
  );
}
