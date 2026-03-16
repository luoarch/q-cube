'use client';

import { useState, useCallback } from 'react';
import Link from 'next/link';

import { useThesisRubrics, useUpsertRubric, useSuggestRubric } from '../../../../src/hooks/api/useThesisRubrics';

import type { RubricScoreResponse } from '@q3/shared-contracts';
import type { RubricSuggestion } from '../../../../src/hooks/api/useThesisRubrics';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const F21_DIMENSIONS = [
  { key: 'usd_debt_exposure', label: 'USD Debt Exposure', hint: 'Dívida em dólar / dívida total. Alto = mais frágil.' },
  { key: 'usd_import_dependence', label: 'USD Import Dependence', hint: 'Importações dolarizadas / custo total. Alto = mais frágil.' },
  { key: 'usd_revenue_offset', label: 'USD Revenue Offset', hint: 'Receita em dólar / receita total. Alto = proteção natural.' },
] as const;

const AI_SUGGEST_DIMENSIONS = new Set(['usd_debt_exposure', 'usd_import_dependence', 'usd_revenue_offset']);
const CONFIDENCE_OPTIONS = ['high', 'medium', 'low'] as const;
const SOURCE_OPTIONS = ['RUBRIC_MANUAL', 'AI_ASSISTED'] as const;
const RUBRIC_VERSION = 'rubric-ui-v1';

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const card = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  padding: '1rem 1.25rem',
} as const;

const inputStyle = {
  padding: '6px 12px',
  background: 'var(--bg-canvas)',
  color: 'var(--text-primary)',
  border: '1px solid var(--border-color)',
  borderRadius: 6,
  fontSize: 13,
  width: '100%',
  boxSizing: 'border-box' as const,
} as const;

const selectStyle = { ...inputStyle } as const;

const btnPrimary = {
  padding: '8px 20px',
  background: 'var(--accent-gold)',
  color: '#0a0e1a',
  border: 'none',
  borderRadius: 6,
  fontWeight: 600,
  cursor: 'pointer',
  fontSize: 13,
} as const;

const btnSecondary = {
  ...btnPrimary,
  background: 'transparent',
  color: 'var(--text-primary)',
  border: '1px solid var(--border-color)',
} as const;

const labelStyle = {
  fontSize: 11,
  color: 'var(--text-secondary)',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.05em',
  marginBottom: 4,
  display: 'block',
} as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DimensionForm {
  score: string;
  sourceType: 'RUBRIC_MANUAL' | 'AI_ASSISTED';
  confidence: 'high' | 'medium' | 'low';
  evidenceRef: string;
  rationale: string;
}

function emptyForm(): DimensionForm {
  return { score: '', sourceType: 'RUBRIC_MANUAL', confidence: 'medium', evidenceRef: '', rationale: '' };
}

function formFromRubric(r: RubricScoreResponse): DimensionForm {
  return {
    score: String(r.score),
    sourceType: (r.sourceType === 'AI_ASSISTED' ? 'AI_ASSISTED' : 'RUBRIC_MANUAL'),
    confidence: (r.confidence as DimensionForm['confidence']) || 'medium',
    evidenceRef: r.evidenceRef ?? '',
    rationale: r.rationale ?? '',
  };
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ThesisRubricsPage() {
  const [tickerInput, setTickerInput] = useState('');
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const [forms, setForms] = useState<Record<string, DimensionForm>>({});
  const [saveStatus, setSaveStatus] = useState<Record<string, 'idle' | 'saving' | 'saved' | 'error'>>({});
  const [suggestions, setSuggestions] = useState<Record<string, RubricSuggestion>>({});

  const { data, isLoading, error } = useThesisRubrics(activeTicker);
  const upsert = useUpsertRubric();
  const suggest = useSuggestRubric();

  const handleSearch = useCallback(() => {
    const t = tickerInput.trim().toUpperCase();
    if (!t) return;
    setActiveTicker(t);
    setForms({});
    setSaveStatus({});
    setSuggestions({});
  }, [tickerInput]);

  // Populate forms from loaded rubrics
  const getForm = useCallback((dimKey: string): DimensionForm => {
    if (forms[dimKey]) return forms[dimKey];
    const existing = data?.rubrics.find((r) => r.dimensionKey === dimKey);
    return existing ? formFromRubric(existing) : emptyForm();
  }, [forms, data]);

  const updateForm = useCallback((dimKey: string, patch: Partial<DimensionForm>) => {
    setForms((prev) => ({
      ...prev,
      [dimKey]: { ...getForm(dimKey), ...patch },
    }));
    setSaveStatus((prev) => ({ ...prev, [dimKey]: 'idle' }));
  }, [getForm]);

  const handleSave = useCallback((dimKey: string) => {
    if (!data?.issuerId) return;
    const form = getForm(dimKey);
    const scoreNum = Number(form.score);
    if (isNaN(scoreNum) || scoreNum < 0 || scoreNum > 100) return;

    setSaveStatus((prev) => ({ ...prev, [dimKey]: 'saving' }));

    upsert.mutate(
      {
        issuerId: data.issuerId,
        dimensionKey: dimKey,
        score: scoreNum,
        sourceType: form.sourceType,
        sourceVersion: RUBRIC_VERSION,
        confidence: form.confidence,
        evidenceRef: form.evidenceRef || null,
        rationale: form.rationale || null,
        assessedAt: new Date().toISOString(),
      },
      {
        onSuccess: () => setSaveStatus((prev) => ({ ...prev, [dimKey]: 'saved' })),
        onError: () => setSaveStatus((prev) => ({ ...prev, [dimKey]: 'error' })),
      },
    );
  }, [data, getForm, upsert]);

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Thesis Rubrics</h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            F2.1 — USD fragility manual scoring
          </p>
        </div>
      </header>

      <div style={{ padding: '1.5rem', flex: 1, overflow: 'auto' }}>
        {/* Search bar */}
        <div style={{ display: 'flex', gap: 8, maxWidth: 420, marginBottom: '1.5rem' }}>
          <input
            type="text"
            placeholder="Ticker (ex: VALE3)"
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            style={inputStyle}
          />
          <button onClick={handleSearch} style={btnPrimary}>
            Buscar
          </button>
        </div>

        {/* States */}
        {!activeTicker && (
          <div style={{ ...card, color: 'var(--text-secondary)', textAlign: 'center', padding: '3rem' }}>
            Digite um ticker para carregar as rubricas de fragilidade USD.
          </div>
        )}

        {isLoading && (
          <div style={{ color: 'var(--text-secondary)' }}>Carregando...</div>
        )}

        {error && (
          <div style={{ ...card, borderColor: '#ef4444', color: '#ef4444' }}>
            {error instanceof Error && error.message.includes('404')
              ? `Ticker "${activeTicker}" não encontrado no universo.`
              : `Erro: ${error.message}`}
          </div>
        )}

        {data && (
          <>
            {/* Issuer info bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: '1rem' }}>
              <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'monospace' }}>{data.ticker}</span>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                issuer: {data.issuerId.slice(0, 8)}…
              </span>
              <Link
                href={`/assets/${data.ticker}`}
                style={{ fontSize: 12, color: 'var(--accent-gold)', textDecoration: 'none' }}
              >
                Ver detalhe →
              </Link>
            </div>

            {/* Dimension cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {F21_DIMENSIONS.map((dim) => {
                const form = getForm(dim.key);
                const existing = data.rubrics.find((r) => r.dimensionKey === dim.key);
                const status = saveStatus[dim.key] ?? 'idle';
                const scoreValid = form.score === '' || (!isNaN(Number(form.score)) && Number(form.score) >= 0 && Number(form.score) <= 100);

                return (
                  <div key={dim.key} style={card}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 600 }}>{dim.label}</div>
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{dim.hint}</div>
                      </div>
                      {existing && (
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', textAlign: 'right' }}>
                          <div>Ativa: score {existing.score} ({existing.sourceType})</div>
                          <div>Criada: {existing.createdAt.slice(0, 10)}</div>
                        </div>
                      )}
                      {!existing && (
                        <span style={{
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 4,
                          background: '#ef444418',
                          color: '#ef4444',
                        }}>
                          DEFAULT
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 }}>
                      {/* Score */}
                      <div>
                        <label style={labelStyle}>Score (0–100)</label>
                        <input
                          type="number"
                          min={0}
                          max={100}
                          step={1}
                          value={form.score}
                          onChange={(e) => updateForm(dim.key, { score: e.target.value })}
                          style={{
                            ...inputStyle,
                            borderColor: scoreValid ? 'var(--border-color)' : '#ef4444',
                          }}
                          placeholder={existing ? String(existing.score) : '—'}
                        />
                      </div>

                      {/* Source type */}
                      <div>
                        <label style={labelStyle}>Source</label>
                        <select
                          value={form.sourceType}
                          onChange={(e) => updateForm(dim.key, { sourceType: e.target.value as DimensionForm['sourceType'] })}
                          style={selectStyle}
                        >
                          {SOURCE_OPTIONS.map((s) => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </select>
                      </div>

                      {/* Confidence */}
                      <div>
                        <label style={labelStyle}>Confidence</label>
                        <select
                          value={form.confidence}
                          onChange={(e) => updateForm(dim.key, { confidence: e.target.value as DimensionForm['confidence'] })}
                          style={selectStyle}
                        >
                          {CONFIDENCE_OPTIONS.map((c) => (
                            <option key={c} value={c}>{c}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                      {/* Evidence ref */}
                      <div>
                        <label style={labelStyle}>Evidence Ref</label>
                        <input
                          type="text"
                          value={form.evidenceRef}
                          onChange={(e) => updateForm(dim.key, { evidenceRef: e.target.value })}
                          style={inputStyle}
                          placeholder="link ou referência"
                        />
                      </div>

                      {/* Rationale */}
                      <div>
                        <label style={labelStyle}>Rationale</label>
                        <input
                          type="text"
                          value={form.rationale}
                          onChange={(e) => updateForm(dim.key, { rationale: e.target.value })}
                          style={inputStyle}
                          placeholder="justificativa curta"
                        />
                      </div>
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <button
                        onClick={() => handleSave(dim.key)}
                        disabled={!form.score || !scoreValid || status === 'saving'}
                        style={{
                          ...btnPrimary,
                          opacity: (!form.score || !scoreValid || status === 'saving') ? 0.4 : 1,
                        }}
                      >
                        {status === 'saving' ? 'Salvando...' : 'Salvar'}
                      </button>
                      <button
                        onClick={() => {
                          setForms((prev) => {
                            const next = { ...prev };
                            delete next[dim.key];
                            return next;
                          });
                          setSaveStatus((prev) => ({ ...prev, [dim.key]: 'idle' }));
                        }}
                        style={btnSecondary}
                      >
                        Reset
                      </button>
                      {AI_SUGGEST_DIMENSIONS.has(dim.key) && (
                        <button
                          onClick={() => {
                            if (!activeTicker) return;
                            suggest.mutate({ ticker: activeTicker, dimension: dim.key }, {
                              onSuccess: (s) => setSuggestions((prev) => ({ ...prev, [dim.key]: s })),
                            });
                          }}
                          disabled={suggest.isPending}
                          style={{
                            ...btnSecondary,
                            borderColor: '#8b5cf6',
                            color: '#8b5cf6',
                            opacity: suggest.isPending ? 0.4 : 1,
                          }}
                        >
                          {suggest.isPending ? 'Gerando...' : 'AI Suggest'}
                        </button>
                      )}
                      {status === 'saved' && (
                        <span style={{ fontSize: 12, color: '#22c55e' }}>Salvo com sucesso</span>
                      )}
                      {status === 'error' && (
                        <span style={{ fontSize: 12, color: '#ef4444' }}>Erro ao salvar</span>
                      )}
                    </div>

                    {/* AI Suggestion panel */}
                    {AI_SUGGEST_DIMENSIONS.has(dim.key) && suggest.isError && (
                      <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 6, background: '#ef444418', color: '#ef4444', fontSize: 12 }}>
                        Erro ao gerar sugestão: {suggest.error?.message}
                      </div>
                    )}
                    {(() => {
                      const sug = suggestions[dim.key];
                      if (!sug) return null;
                      return (
                      <div style={{
                        marginTop: 12,
                        padding: '12px 16px',
                        borderRadius: 6,
                        border: '1px solid #8b5cf6',
                        background: '#8b5cf608',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: '#8b5cf6' }}>
                            AI Suggestion — score {sug.suggestedScore}
                          </span>
                          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                            {sug.confidence} confidence · {sug.modelUsed}
                          </span>
                        </div>

                        <div style={{ fontSize: 12, color: 'var(--text-primary)', marginBottom: 8, lineHeight: 1.5 }}>
                          {sug.rationale}
                        </div>

                        {sug.keySignals.length > 0 && (
                          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
                            <strong>Signals:</strong> {sug.keySignals.join(', ')}
                          </div>
                        )}
                        {sug.uncertaintyFactors.length > 0 && (
                          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8 }}>
                            <strong>Uncertainties:</strong> {sug.uncertaintyFactors.join(', ')}
                          </div>
                        )}

                        <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 10 }}>
                          prompt: {sug.promptVersion} · cost: ${sug.costUsd.toFixed(4)} · ref: {sug.evidenceRef}
                        </div>

                        <div style={{ display: 'flex', gap: 8 }}>
                          <button
                            onClick={() => {
                              updateForm(dim.key, {
                                score: String(sug.suggestedScore),
                                sourceType: 'AI_ASSISTED',
                                confidence: sug.confidence as DimensionForm['confidence'],
                                evidenceRef: sug.evidenceRef,
                                rationale: `[AI] ${sug.rationale}`,
                              });
                              setSuggestions((prev) => { const n = { ...prev }; delete n[dim.key]; return n; });
                            }}
                            style={{ ...btnPrimary, fontSize: 12, padding: '6px 16px', background: '#22c55e' }}
                          >
                            Accept
                          </button>
                          <button
                            onClick={() => {
                              updateForm(dim.key, {
                                score: String(sug.suggestedScore),
                                sourceType: 'RUBRIC_MANUAL',
                                confidence: sug.confidence as DimensionForm['confidence'],
                                evidenceRef: sug.evidenceRef,
                                rationale: `[AI-edited] ${sug.rationale}`,
                              });
                              setSuggestions((prev) => { const n = { ...prev }; delete n[dim.key]; return n; });
                            }}
                            style={{ ...btnSecondary, fontSize: 12, padding: '6px 16px' }}
                          >
                            Edit &amp; Review
                          </button>
                          <button
                            onClick={() => setSuggestions((prev) => { const n = { ...prev }; delete n[dim.key]; return n; })}
                            style={{ ...btnSecondary, fontSize: 12, padding: '6px 16px', borderColor: '#ef4444', color: '#ef4444' }}
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                      );
                    })()}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
