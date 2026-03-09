'use client';

import Link from 'next/link';
import { useCallback, useMemo, useState } from 'react';

import styles from './profile.module.css';
import { useUpdateUserContext, useUserContext } from '../../../src/hooks/api/useUserContext';

import type { UpdateUserContext } from '@q3/shared-contracts';

const STRATEGY_OPTIONS = [
  { value: 'magic_formula_original', label: 'Magic Formula (Original)' },
  { value: 'magic_formula_brazil', label: 'Magic Formula (Brasil)' },
] as const;

const CHAT_MODE_OPTIONS = [
  { value: 'free_chat', label: 'Chat Livre' },
  { value: 'agent_solo', label: 'Agente Solo' },
  { value: 'roundtable', label: 'Mesa Redonda' },
  { value: 'debate', label: 'Debate' },
  { value: 'comparison', label: 'Comparacao' },
] as const;

const AGENT_OPTIONS = [
  { value: 'barsi', label: 'Barsi-inspired' },
  { value: 'graham', label: 'Graham-inspired' },
  { value: 'greenblatt', label: 'Greenblatt-inspired' },
  { value: 'buffett', label: 'Buffett-inspired' },
] as const;

export default function ProfilePage() {
  const { data: profile, isLoading } = useUserContext();
  const updateMutation = useUpdateUserContext();

  const defaults = useMemo(() => ({
    strategy: profile?.preferredStrategy ?? null,
    watchlist: (profile?.watchlistJson ?? []).join(', '),
    chatMode: profile?.preferencesJson?.defaultChatMode ?? '',
    agents: profile?.preferencesJson?.favoriteAgents ?? [],
  }), [profile]);

  const [preferredStrategy, setPreferredStrategy] = useState<string | null>(null);
  const [watchlist, setWatchlist] = useState('');
  const [defaultChatMode, setDefaultChatMode] = useState('');
  const [favoriteAgents, setFavoriteAgents] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [initialized, setInitialized] = useState(false);

  // Sync from server data once on first load
  if (profile && !initialized) {
    setPreferredStrategy(defaults.strategy);
    setWatchlist(defaults.watchlist);
    setDefaultChatMode(defaults.chatMode);
    setFavoriteAgents(defaults.agents);
    setInitialized(true);
  }

  const handleAgentToggle = useCallback((agentId: string) => {
    setFavoriteAgents((prev) =>
      prev.includes(agentId) ? prev.filter((a) => a !== agentId) : [...prev, agentId],
    );
  }, []);

  const handleSave = useCallback(() => {
    const tickerList = watchlist
      .split(/[,;\s]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);

    const payload: UpdateUserContext = {
      preferredStrategy: preferredStrategy || null,
      watchlistJson: tickerList.length > 0 ? tickerList : null,
      preferencesJson: {
        defaultChatMode: defaultChatMode || undefined,
        favoriteAgents: favoriteAgents.length > 0 ? favoriteAgents : undefined,
      },
    };

    updateMutation.mutate(payload, {
      onSuccess: () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      },
    });
  }, [preferredStrategy, watchlist, defaultChatMode, favoriteAgents, updateMutation]);

  if (isLoading) {
    return (
      <div className="dashboard-page">
        <header className="dashboard-header">
          <Link href="/ranking" className={styles.backLink}>
            ← Ranking
          </Link>
          <h1>Perfil</h1>
        </header>
        <div className={styles.container}>
          <div className={styles.skeleton} />
          <div className={styles.skeleton} />
          <div className={styles.skeleton} />
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <Link href="/ranking" className={styles.backLink}>
          ← Ranking
        </Link>
        <h1>Perfil</h1>
      </header>

      <div className={styles.container}>
        {/* Strategy */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Estrategia Preferida</h2>
          <select
            value={preferredStrategy ?? ''}
            onChange={(e) => setPreferredStrategy(e.target.value || null)}
            className={styles.select}
          >
            <option value="">Nenhuma</option>
            {STRATEGY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </section>

        {/* Watchlist */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Watchlist</h2>
          <p className={styles.hint}>Tickers separados por virgula (max 50)</p>
          <input
            type="text"
            value={watchlist}
            onChange={(e) => setWatchlist(e.target.value)}
            placeholder="WEGE3, BBAS3, ITUB4, RENT3"
            className={styles.input}
          />
        </section>

        {/* Default chat mode */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Modo de Chat Padrao</h2>
          <select
            value={defaultChatMode}
            onChange={(e) => setDefaultChatMode(e.target.value)}
            className={styles.select}
          >
            <option value="">Padrao (Chat Livre)</option>
            {CHAT_MODE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </section>

        {/* Favorite agents */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Agentes Favoritos</h2>
          <div className={styles.agentGrid}>
            {AGENT_OPTIONS.map((agent) => (
              <label key={agent.value} className={styles.agentChip}>
                <input
                  type="checkbox"
                  checked={favoriteAgents.includes(agent.value)}
                  onChange={() => handleAgentToggle(agent.value)}
                  className={styles.srOnly}
                />
                <span
                  className={`${styles.chipLabel} ${favoriteAgents.includes(agent.value) ? styles.chipActive : ''}`}
                >
                  {agent.label}
                </span>
              </label>
            ))}
          </div>
        </section>

        {/* Save */}
        <div className={styles.actions}>
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className={styles.saveButton}
          >
            {updateMutation.isPending ? 'Salvando...' : saved ? 'Salvo!' : 'Salvar'}
          </button>
          {updateMutation.isError && (
            <p className={styles.error}>Erro ao salvar. Tente novamente.</p>
          )}
        </div>
      </div>
    </div>
  );
}
