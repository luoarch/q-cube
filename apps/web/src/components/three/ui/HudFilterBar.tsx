'use client';

import { useSceneStore } from '../../../stores/sceneStore';

export function HudFilterBar({ sectors }: { sectors: string[] }) {
  const filters = useSceneStore((s) => s.filters);
  const setFilter = useSceneStore((s) => s.setFilter);
  const clearFilters = useSceneStore((s) => s.clearFilters);

  return (
    <div
      style={{
        position: 'absolute',
        top: 16,
        left: 16,
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
        zIndex: 10,
      }}
    >
      <button
        onClick={clearFilters}
        className="filter-chip"
        data-active={!filters.sector && !filters.quality && !filters.liquidity}
      >
        Todos
      </button>
      {sectors.map((sector) => (
        <button
          key={sector}
          onClick={() => setFilter('sector', filters.sector === sector ? null : sector)}
          className="filter-chip"
          data-active={filters.sector === sector}
        >
          {sector}
        </button>
      ))}
      {(['high', 'medium', 'low'] as const).map((q) => (
        <button
          key={q}
          onClick={() => setFilter('quality', filters.quality === q ? null : q)}
          className="filter-chip"
          data-active={filters.quality === q}
        >
          Quality: {q}
        </button>
      ))}
      <style>{`
        .filter-chip {
          background: rgba(10, 14, 26, 0.85);
          color: var(--text-secondary, #94a3b8);
          border: 1px solid var(--border-color, rgba(148,163,184,0.15));
          padding: 4px 12px;
          border-radius: 16px;
          font-size: 12px;
          font-family: inherit;
          cursor: pointer;
          backdrop-filter: blur(8px);
          transition: all 0.2s;
        }
        .filter-chip:hover {
          border-color: var(--accent-gold, #fbbf24);
          color: var(--text-primary, #e2e8f0);
        }
        .filter-chip[data-active="true"] {
          background: var(--accent-gold, #fbbf24);
          color: #0a0e1a;
          border-color: var(--accent-gold, #fbbf24);
        }
      `}</style>
    </div>
  );
}
