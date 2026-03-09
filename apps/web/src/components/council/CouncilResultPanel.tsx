'use client';


import { AgentCard } from './AgentCard';
import { ConflictMatrix } from './ConflictMatrix';
import styles from './council.module.css';
import { DebateTimeline } from './DebateTimeline';
import { Scoreboard } from './Scoreboard';

import type {
  AgentOpinion,
  ConflictEntry,
  CouncilScoreboard,
  DebateRound,
  ModeratorSynthesis,
} from '@q3/shared-contracts';

export type CouncilData = {
  opinions?: AgentOpinion[];
  scoreboard?: CouncilScoreboard;
  conflictMatrix?: ConflictEntry[];
  moderatorSynthesis?: ModeratorSynthesis;
  debateLog?: DebateRound[];
};

export function CouncilResultPanel({ data }: { data: CouncilData }) {
  return (
    <div className={styles.councilResultPanel}>
      <Scoreboard scoreboard={data.scoreboard} />
      <ConflictMatrix conflicts={data.conflictMatrix ?? []} />
      <DebateTimeline rounds={data.debateLog ?? []} />

      {/* Moderator Synthesis */}
      {data.moderatorSynthesis?.overallAssessment && (
        <div className={styles.synthesisPanel}>
          <div className={styles.synthesisTitle}>Sintese do Moderador</div>
          <div className={styles.synthesisText}>
            {data.moderatorSynthesis.overallAssessment}
          </div>

          {data.moderatorSynthesis.convergences?.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div className={`${styles.sectionLabel} ${styles.sectionLabelFor}`}>Convergencias</div>
              <ul className={styles.sectionList}>
                {data.moderatorSynthesis.convergences.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}

          {data.moderatorSynthesis.biggestRisk && (
            <div className={styles.synthesisRisk}>
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
