'use client';

import { useState } from 'react';


import { AGENT_LABELS } from './constants';
import styles from './council.module.css';
import { VerdictChip } from './VerdictChip';

import type { AgentOpinion } from '@q3/shared-contracts';

export function AgentCard({
  opinion,
  defaultExpanded = false,
}: {
  opinion: AgentOpinion;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div
      className={styles.agentCard}
      style={{ '--verdict-color': getVerdictColor(opinion.verdict) } as React.CSSProperties}
    >
      <button
        className={styles.agentCardHeader}
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-controls={`agent-${opinion.agentId}-body`}
      >
        <div className={styles.agentCardHeaderLeft}>
          <span className={styles.agentCardName}>
            {AGENT_LABELS[opinion.agentId] ?? opinion.agentId}
          </span>
          <VerdictChip verdict={opinion.verdict} confidence={opinion.confidence} />
        </div>
        <span className={`${styles.agentCardToggle} ${expanded ? styles.agentCardToggleOpen : ''}`}>
          ▾
        </span>
      </button>

      {expanded && (
        <div id={`agent-${opinion.agentId}-body`} className={styles.agentCardBody} role="region">
          {/* Thesis */}
          <div className={styles.thesis}>{opinion.thesis}</div>

          {/* Reasons For */}
          {opinion.reasonsFor?.length > 0 && (
            <div>
              <div className={`${styles.sectionLabel} ${styles.sectionLabelFor}`}>A Favor</div>
              <ul className={styles.sectionList}>
                {opinion.reasonsFor.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Reasons Against */}
          {opinion.reasonsAgainst?.length > 0 && (
            <div>
              <div className={`${styles.sectionLabel} ${styles.sectionLabelAgainst}`}>Contra</div>
              <ul className={styles.sectionList}>
                {opinion.reasonsAgainst.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Key Metrics */}
          {opinion.keyMetricsUsed?.length > 0 && (
            <div>
              <div className={`${styles.sectionLabel} ${styles.sectionLabelMuted}`}>
                Metricas Utilizadas
              </div>
              <div className={styles.badgeRow}>
                {opinion.keyMetricsUsed.map((m) => (
                  <span key={m} className={styles.badge}>{m}</span>
                ))}
              </div>
            </div>
          )}

          {/* Hard Rejects */}
          {opinion.hardRejectsTriggered?.length > 0 && (
            <div>
              <div className={`${styles.sectionLabel} ${styles.sectionLabelAgainst}`}>
                Rejeicoes Automaticas
              </div>
              <ul className={styles.sectionList}>
                {opinion.hardRejectsTriggered.map((r, i) => (
                  <li key={i} className={styles.rejectItem}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* What Would Change My Mind */}
          {opinion.whatWouldChangeMyMind?.length > 0 && (
            <div>
              <div className={`${styles.sectionLabel} ${styles.sectionLabelGold}`}>
                O que mudaria minha opiniao
              </div>
              <ul className={styles.sectionList}>
                {opinion.whatWouldChangeMyMind.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Unknowns */}
          {opinion.unknowns?.length > 0 && (
            <div>
              <div className={`${styles.sectionLabel} ${styles.sectionLabelMuted}`}>Incertezas</div>
              <ul className={styles.sectionList}>
                {opinion.unknowns.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Investor Fit */}
          {opinion.investorFit?.length > 0 && (
            <div>
              <div className={`${styles.sectionLabel} ${styles.sectionLabelMuted}`}>
                Perfil do Investidor
              </div>
              <div className={styles.badgeRow}>
                {opinion.investorFit.map((f) => (
                  <span key={f} className={`${styles.badge} ${styles.badgeGold}`}>{f}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function getVerdictColor(verdict: string): string {
  const colors: Record<string, string> = {
    buy: '#22c55e',
    watch: '#fbbf24',
    avoid: '#ef4444',
    insufficient_data: '#94a3b8',
  };
  return colors[verdict] ?? '#94a3b8';
}
