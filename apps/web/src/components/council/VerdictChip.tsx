'use client';

import type { AgentVerdict } from '@q3/shared-contracts';

import { VERDICT_COLORS, VERDICT_LABELS } from './constants';

import styles from './council.module.css';

export function VerdictChip({ verdict, confidence }: { verdict: AgentVerdict; confidence: number }) {
  const color = VERDICT_COLORS[verdict] ?? '#94a3b8';
  return (
    <span
      className={styles.verdictChip}
      style={{ '--verdict-color': color } as React.CSSProperties}
    >
      {VERDICT_LABELS[verdict] ?? verdict}
      <span className={styles.verdictConfidence}>{confidence}%</span>
    </span>
  );
}
