'use client';

import { useState } from 'react';

import {
  useStrategyRegistry,
  getStatusLabel,
  getStatusColor,
  type StrategyRegistryEntry,
} from '../hooks/api/useStrategyRegistry';

/**
 * Match a run/strategy config against the registry.
 * Returns the matching entry or null if no registered config matches.
 */
function matchByType(
  strategyType: string,
  registry: StrategyRegistryEntry[] | undefined,
): StrategyRegistryEntry[] {
  if (!registry) return [];
  return registry.filter((e) => e.strategyType === strategyType);
}

export type WarningLevel = 'none' | 'info' | 'warn' | 'danger';

interface WarningGateProps {
  strategyType: string;
  onConfirm: () => void;
  isPending?: boolean;
  buttonLabel?: string;
  onWarningLevel?: (level: WarningLevel) => void;
}

// Per-strategy_type ack with 10-minute TTL
const ackCache = new Map<string, number>();
const ACK_TTL_MS = 10 * 60 * 1000; // 10 minutes

function isAcked(strategyType: string): boolean {
  const ts = ackCache.get(strategyType);
  if (!ts) return false;
  if (Date.now() - ts > ACK_TTL_MS) {
    ackCache.delete(strategyType);
    return false;
  }
  return true;
}

function setAcked(strategyType: string) {
  ackCache.set(strategyType, Date.now());
}

/**
 * Soft enforcement gate for strategy execution.
 *
 * - REJECTED/BLOCKED configs → warning modal requiring explicit acknowledgment
 * - PROMOTED configs → proceeds, but shows info badge if REJECTED siblings exist
 * - Unregistered strategies → warning as UNVALIDATED
 * - Ack is per strategy_type with 10-minute TTL (not session-wide)
 *
 * Returns `lastWarningLevel` via callback so parent can persist visual context.
 */
export function StrategyWarningGate({ strategyType, onConfirm, isPending, buttonLabel, onWarningLevel }: WarningGateProps) {
  const { data: registry } = useStrategyRegistry();
  const [showWarning, setShowWarning] = useState(false);

  const entries = matchByType(strategyType, registry);
  const hasPromoted = entries.some((e) => e.promotionStatus === 'PROMOTED');
  const allRejected = entries.length > 0 && entries.every((e) => e.promotionStatus === 'REJECTED');
  const hasBlocked = entries.some((e) => e.promotionStatus === 'BLOCKED');
  const isUnvalidated = entries.length === 0;

  // Warning level: determines if modal is needed
  // "none" = promoted with no rejected siblings, or already acked
  // "info" = promoted but has rejected siblings (no modal, just badge)
  // "warn" = blocked or unvalidated
  // "danger" = all rejected
  const warningLevel = isUnvalidated
    ? 'warn'
    : allRejected
      ? 'danger'
      : hasPromoted && !entries.some((e) => e.promotionStatus === 'REJECTED')
        ? 'none'
        : hasPromoted
          ? 'info'
          : 'warn';

  const needsModal = warningLevel === 'danger' || warningLevel === 'warn';

  const handleClick = () => {
    onWarningLevel?.(warningLevel);
    if (!needsModal || isAcked(strategyType)) {
      onConfirm();
      return;
    }
    setShowWarning(true);
  };

  const handleAcknowledge = () => {
    setAcked(strategyType);
    setShowWarning(false);
    onConfirm();
  };

  const borderColor = allRejected ? '#ef4444' : hasBlocked ? '#fbbf24' : 'var(--accent-gold)';
  const bgColor = allRejected ? 'var(--accent-gold)' : hasBlocked ? 'var(--accent-gold)' : 'var(--accent-gold)';

  const modalBorderColor = allRejected || (isUnvalidated) ? '#ef4444' : '#fbbf24';

  return (
    <>
      <button
        onClick={handleClick}
        disabled={isPending}
        style={{
          padding: '0.5rem 1.25rem',
          background: bgColor,
          color: '#0a0e1a',
          border: 'none',
          borderRadius: 6,
          fontWeight: 600,
          fontSize: 14,
          cursor: isPending ? 'wait' : 'pointer',
          opacity: isPending ? 0.7 : 1,
        }}
      >
        {isPending ? 'Executando...' : buttonLabel ?? 'Executar'}
      </button>

      {/* Warning modal */}
      {showWarning && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(0,0,0,0.6)',
          }}
        >
          <div
            style={{
              background: 'var(--bg-surface, #1e293b)',
              border: `2px solid ${modalBorderColor}`,
              borderRadius: 12,
              padding: '1.5rem',
              maxWidth: 520,
              width: '90%',
              color: 'var(--text-primary, #e2e8f0)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
                {isUnvalidated
                  ? 'Estratégia não validada empiricamente'
                  : allRejected
                    ? 'Estratégia sem evidência OOS robusta'
                    : 'Estratégia não promovida'}
              </h3>
            </div>

            {isUnvalidated ? (
              <div
                style={{
                  padding: '0.5rem 0.75rem',
                  marginBottom: '0.5rem',
                  background: 'rgba(148,163,184,0.08)',
                  border: '1px solid rgba(148,163,184,0.2)',
                  borderRadius: 6,
                }}
              >
                <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                  Esta configuração de estratégia ainda não passou por validação empírica.
                  Não há evidência para ou contra — os resultados devem ser interpretados com cautela.
                </p>
              </div>
            ) : (
              <div style={{ marginBottom: '1rem' }}>
                {entries.map((e) => {
                  const color = getStatusColor(e.promotionStatus);
                  return (
                    <div
                      key={e.strategyFingerprint}
                      style={{
                        padding: '0.5rem 0.75rem',
                        marginBottom: '0.5rem',
                        background: `${color}0a`,
                        border: `1px solid ${color}30`,
                        borderRadius: 6,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.25rem' }}>
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
                        <strong style={{ fontSize: 13 }}>{e.strategyKey}</strong>
                        <span style={{ fontSize: 12, color }}>{getStatusLabel(e.role, e.promotionStatus)}</span>
                      </div>
                      <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                        {e.evidenceSummary}
                      </p>
                      {e.oosSharpeAvg != null && (
                        <div style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                          OOS Sharpe avg: {e.oosSharpeAvg.toFixed(4)}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 1rem', lineHeight: 1.5 }}>
              {isUnvalidated
                ? 'Nenhuma configuração desta família foi avaliada. Os resultados não devem ser tratados como evidência empírica.'
                : allRejected
                  ? 'Esta configuração não apresentou evidência robusta fora da amostra. Você pode continuar para fins de pesquisa, mas os resultados não suportam claims de performance.'
                  : 'O candidato líder de pesquisa ainda não atingiu o limiar de promoção. Prossiga com consciência das limitações metodológicas.'}
            </p>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowWarning(false)}
                style={{
                  padding: '0.5rem 1rem',
                  background: 'transparent',
                  border: '1px solid var(--border-color)',
                  borderRadius: 6,
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontSize: 13,
                }}
              >
                Cancelar
              </button>
              <button
                onClick={handleAcknowledge}
                style={{
                  padding: '0.5rem 1rem',
                  background: allRejected ? '#ef4444' : '#fbbf24',
                  color: '#0a0e1a',
                  border: 'none',
                  borderRadius: 6,
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontSize: 13,
                }}
              >
                Entendo, prosseguir
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/**
 * Persistent banner shown AFTER execution to remind the user of the strategy's empirical status.
 * This ensures the warning context doesn't disappear after acknowledgment.
 */
export function StrategyExecutionBanner({ strategyType }: { strategyType: string }) {
  const { data: registry } = useStrategyRegistry();
  const entries = matchByType(strategyType, registry);

  if (!entries.length && !registry) return null;

  const isUnvalidated = entries.length === 0 && registry && registry.length > 0;
  const allRejected = entries.length > 0 && entries.every((e) => e.promotionStatus === 'REJECTED');
  const hasBlocked = entries.some((e) => e.promotionStatus === 'BLOCKED');
  const hasPromoted = entries.some((e) => e.promotionStatus === 'PROMOTED');

  if (hasPromoted && !entries.some((e) => e.promotionStatus === 'REJECTED')) return null;

  const color = allRejected ? '#ef4444' : hasBlocked ? '#fbbf24' : isUnvalidated ? '#94a3b8' : '#fbbf24';
  const message = allRejected
    ? 'Resultados de estratégia sem evidência OOS robusta — não suportam claims de performance'
    : isUnvalidated
      ? 'Estratégia não validada empiricamente — resultados devem ser interpretados com cautela'
      : hasBlocked
        ? 'Estratégia não promovida — candidato líder de pesquisa, limiar de promoção não atingido'
        : 'Estratégia contém configurações com status misto — verifique o registry';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.35rem 1rem',
        background: `${color}0a`,
        borderBottom: `2px solid ${color}30`,
        fontSize: 12,
        color,
        fontWeight: 600,
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
      {message}
    </div>
  );
}
