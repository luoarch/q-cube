import {
  boolean,
  date,
  integer,
  jsonb,
  numeric,
  pgEnum,
  pgTable,
  text,
  timestamp,
  unique,
  uuid,
  varchar,
} from 'drizzle-orm/pg-core';

export const membershipRoleEnum = pgEnum('membership_role', ['owner', 'admin', 'member', 'viewer']);

export const strategyTypeEnum = pgEnum('strategy_type', [
  'magic_formula_original',
  'magic_formula_brazil',
  'magic_formula_hybrid',
]);

export const runStatusEnum = pgEnum('run_status', ['pending', 'running', 'completed', 'failed']);

export const jobKindEnum = pgEnum('job_kind', ['strategy_run', 'backtest_run']);

export const tenants = pgTable('tenants', {
  id: uuid('id').primaryKey(),
  name: text('name').notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const users = pgTable('users', {
  id: uuid('id').primaryKey(),
  email: text('email').notNull().unique(),
  fullName: text('full_name').notNull(),
  passwordHash: text('password_hash'),
  failedLoginAttempts: integer('failed_login_attempts').notNull().default(0),
  lockedUntil: timestamp('locked_until', { withTimezone: true }),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const memberships = pgTable('memberships', {
  id: uuid('id').primaryKey(),
  tenantId: uuid('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  userId: uuid('user_id')
    .notNull()
    .references(() => users.id, { onDelete: 'cascade' }),
  role: membershipRoleEnum('role').notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const assets = pgTable(
  'assets',
  {
    id: uuid('id').primaryKey(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    ticker: text('ticker').notNull(),
    name: text('name').notNull(),
    sector: text('sector'),
    subSector: text('sub_sector'),
    isActive: boolean('is_active').notNull().default(true),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => [unique('uq_assets_tenant_ticker').on(t.tenantId, t.ticker)],
);

export const financialStatements = pgTable(
  'financial_statements',
  {
    id: uuid('id').primaryKey(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    assetId: uuid('asset_id')
      .notNull()
      .references(() => assets.id, { onDelete: 'cascade' }),
    periodDate: timestamp('period_date', { withTimezone: true }).notNull(),
    ebit: numeric('ebit'),
    enterpriseValue: numeric('enterprise_value'),
    netWorkingCapital: numeric('net_working_capital'),
    fixedAssets: numeric('fixed_assets'),
    roic: numeric('roic'),
    netDebt: numeric('net_debt'),
    ebitda: numeric('ebitda'),
    netMargin: numeric('net_margin'),
    grossMargin: numeric('gross_margin'),
    netMarginStd: numeric('net_margin_std'),
    avgDailyVolume: numeric('avg_daily_volume'),
    marketCap: numeric('market_cap'),
    momentum12m: numeric('momentum_12m'),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => [unique('uq_financial_statements_asset_period').on(t.assetId, t.periodDate)],
);

export const strategyRuns = pgTable('strategy_runs', {
  id: uuid('id').primaryKey(),
  tenantId: uuid('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  strategy: strategyTypeEnum('strategy').notNull(),
  status: runStatusEnum('status').notNull(),
  asOfDate: timestamp('as_of_date', { withTimezone: true }),
  errorMessage: text('error_message'),
  resultJson: jsonb('result_json'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const backtestRuns = pgTable('backtest_runs', {
  id: uuid('id').primaryKey(),
  tenantId: uuid('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  status: runStatusEnum('status').notNull(),
  configJson: jsonb('config_json').notNull(),
  metricsJson: jsonb('metrics_json'),
  errorMessage: text('error_message'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const jobs = pgTable('jobs', {
  id: uuid('id').primaryKey(),
  tenantId: uuid('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  kind: jobKindEnum('kind').notNull(),
  status: runStatusEnum('status').notNull(),
  payloadJson: jsonb('payload_json').notNull(),
  errorMessage: text('error_message'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

// ---------------------------------------------------------------------------
// Fundamentals enums (global, not tenant-scoped)
// ---------------------------------------------------------------------------

export const statementTypeEnum = pgEnum('statement_type', [
  'DRE',
  'BPA',
  'BPP',
  'DFC_MD',
  'DFC_MI',
  'DMPL',
  'DVA',
]);

export const periodTypeEnum = pgEnum('period_type', ['annual', 'quarterly']);

export const filingTypeEnum = pgEnum('filing_type', ['DFP', 'ITR', 'FCA']);

export const filingStatusEnum = pgEnum('filing_status', [
  'pending',
  'processing',
  'completed',
  'failed',
  'superseded',
]);

export const batchStatusEnum = pgEnum('batch_status', [
  'pending',
  'downloading',
  'processing',
  'completed',
  'failed',
]);

export const scopeTypeEnum = pgEnum('scope_type', ['con', 'ind']);

export const sourceProviderEnum = pgEnum('source_provider', [
  'cvm',
  'brapi',
  'dados_de_mercado',
  'manual',
  'yahoo',
]);

// ---------------------------------------------------------------------------
// Fundamentals tables (global, NOT tenant-scoped)
// ---------------------------------------------------------------------------

export const rawSourceBatches = pgTable('raw_source_batches', {
  id: uuid('id').primaryKey(),
  source: sourceProviderEnum('source').notNull(),
  year: integer('year').notNull(),
  documentType: filingTypeEnum('document_type').notNull(),
  status: batchStatusEnum('status').notNull(),
  startedAt: timestamp('started_at', { withTimezone: true }).defaultNow().notNull(),
  completedAt: timestamp('completed_at', { withTimezone: true }),
});

export const rawSourceFiles = pgTable('raw_source_files', {
  id: uuid('id').primaryKey(),
  batchId: uuid('batch_id')
    .notNull()
    .references(() => rawSourceBatches.id, { onDelete: 'cascade' }),
  filename: text('filename').notNull(),
  url: text('url').notNull(),
  sha256Hash: varchar('sha256_hash', { length: 64 }).notNull(),
  sizeBytes: integer('size_bytes').notNull(),
  importedAt: timestamp('imported_at', { withTimezone: true }).defaultNow().notNull(),
});

export const issuers = pgTable('issuers', {
  id: uuid('id').primaryKey(),
  cvmCode: text('cvm_code').notNull().unique(),
  legalName: text('legal_name').notNull(),
  tradeName: text('trade_name'),
  cnpj: text('cnpj').notNull().unique(),
  sector: text('sector'),
  subsector: text('subsector'),
  segment: text('segment'),
  status: text('status').notNull().default('active'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const securities = pgTable(
  'securities',
  {
    id: uuid('id').primaryKey(),
    issuerId: uuid('issuer_id')
      .notNull()
      .references(() => issuers.id, { onDelete: 'cascade' }),
    ticker: text('ticker').notNull(),
    securityClass: text('security_class'),
    isPrimary: boolean('is_primary').notNull().default(false),
    validFrom: date('valid_from').notNull(),
    validTo: date('valid_to'),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => [unique('uq_securities_issuer_ticker_valid').on(t.issuerId, t.ticker, t.validFrom)],
);

export const filings = pgTable('filings', {
  id: uuid('id').primaryKey(),
  issuerId: uuid('issuer_id')
    .notNull()
    .references(() => issuers.id, { onDelete: 'cascade' }),
  source: sourceProviderEnum('source').notNull(),
  filingType: filingTypeEnum('filing_type').notNull(),
  referenceDate: date('reference_date').notNull(),
  versionNumber: integer('version_number').notNull().default(1),
  isRestatement: boolean('is_restatement').notNull().default(false),
  supersedesFilingId: uuid('supersedes_filing_id').references((): any => filings.id, {
    onDelete: 'set null',
  }),
  status: filingStatusEnum('status').notNull(),
  rawFileId: uuid('raw_file_id').references(() => rawSourceFiles.id, { onDelete: 'set null' }),
  validationResult: jsonb('validation_result'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const statementLines = pgTable('statement_lines', {
  id: uuid('id').primaryKey(),
  filingId: uuid('filing_id')
    .notNull()
    .references(() => filings.id, { onDelete: 'cascade' }),
  statementType: statementTypeEnum('statement_type').notNull(),
  scope: scopeTypeEnum('scope').notNull(),
  periodType: periodTypeEnum('period_type').notNull(),
  referenceDate: date('reference_date').notNull(),
  canonicalKey: text('canonical_key'),
  asReportedLabel: text('as_reported_label').notNull(),
  asReportedCode: text('as_reported_code').notNull(),
  normalizedValue: numeric('normalized_value'),
  currency: text('currency').notNull().default('BRL'),
  unitScale: text('unit_scale').notNull().default('UNIDADE'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});

export const computedMetrics = pgTable('computed_metrics', {
  id: uuid('id').primaryKey(),
  issuerId: uuid('issuer_id')
    .notNull()
    .references(() => issuers.id, { onDelete: 'cascade' }),
  securityId: uuid('security_id').references(() => securities.id, { onDelete: 'set null' }),
  metricCode: text('metric_code').notNull(),
  periodType: periodTypeEnum('period_type').notNull(),
  referenceDate: date('reference_date').notNull(),
  value: numeric('value'),
  formulaVersion: integer('formula_version').notNull().default(1),
  inputsSnapshotJson: jsonb('inputs_snapshot_json').notNull(),
  sourceFilingIdsJson: jsonb('source_filing_ids_json').notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const restatementEvents = pgTable('restatement_events', {
  id: uuid('id').primaryKey(),
  originalFilingId: uuid('original_filing_id')
    .notNull()
    .references(() => filings.id, { onDelete: 'cascade' }),
  newFilingId: uuid('new_filing_id')
    .notNull()
    .references(() => filings.id, { onDelete: 'cascade' }),
  detectedAt: timestamp('detected_at', { withTimezone: true }).defaultNow().notNull(),
  affectedMetrics: jsonb('affected_metrics').notNull(),
});

export const marketSnapshots = pgTable(
  'market_snapshots',
  {
    id: uuid('id').primaryKey(),
    securityId: uuid('security_id')
      .notNull()
      .references(() => securities.id, { onDelete: 'cascade' }),
    source: sourceProviderEnum('source').notNull(),
    price: numeric('price'),
    marketCap: numeric('market_cap'),
    volume: numeric('volume'),
    currency: varchar('currency', { length: 255 }).notNull().default('BRL'),
    fetchedAt: timestamp('fetched_at', { withTimezone: true }).defaultNow().notNull(),
    rawJson: jsonb('raw_json'),
  },
  (t) => [unique('uq_market_snapshots_security_fetched').on(t.securityId, t.fetchedAt)],
);

// ---------------------------------------------------------------------------
// Embeddings (RAG)
// ---------------------------------------------------------------------------

export const embeddings = pgTable(
  'embeddings',
  {
    id: uuid('id').primaryKey(),
    entityType: varchar('entity_type', { length: 50 }).notNull(),
    entityId: varchar('entity_id', { length: 255 }).notNull(),
    chunkIndex: integer('chunk_index').notNull().default(0),
    chunkText: text('chunk_text').notNull(),
    embedding: jsonb('embedding').notNull(), // VECTOR(1536) when pgvector extension is enabled
    metadataJson: jsonb('metadata_json'),
    modelUsed: varchar('model_used', { length: 50 }).notNull().default('text-embedding-3-small'),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => [unique('uq_embeddings_entity_chunk').on(t.entityType, t.entityId, t.chunkIndex)],
);

// ---------------------------------------------------------------------------
// Refinement results (Top-30 Refiner)
// ---------------------------------------------------------------------------

export const scoreReliabilityEnum = pgEnum('score_reliability', [
  'high',
  'medium',
  'low',
  'unavailable',
]);

export const issuerClassificationEnum = pgEnum('issuer_classification', [
  'non_financial',
  'bank',
  'insurer',
  'utility',
  'holding',
]);

export const refinementResults = pgTable(
  'refinement_results',
  {
    id: uuid('id').primaryKey(),
    strategyRunId: uuid('strategy_run_id')
      .notNull()
      .references(() => strategyRuns.id, { onDelete: 'cascade' }),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    issuerId: uuid('issuer_id')
      .notNull()
      .references(() => issuers.id, { onDelete: 'cascade' }),
    ticker: varchar('ticker', { length: 20 }).notNull(),
    baseRank: integer('base_rank').notNull(),
    earningsQualityScore: numeric('earnings_quality_score'),
    safetyScore: numeric('safety_score'),
    operatingConsistencyScore: numeric('operating_consistency_score'),
    capitalDisciplineScore: numeric('capital_discipline_score'),
    refinementScore: numeric('refinement_score'),
    adjustedScore: numeric('adjusted_score'),
    adjustedRank: integer('adjusted_rank'),
    flagsJson: jsonb('flags_json'),
    trendDataJson: jsonb('trend_data_json'),
    scoringDetailsJson: jsonb('scoring_details_json'),
    dataCompletenessJson: jsonb('data_completeness_json'),
    scoreReliability: varchar('score_reliability', { length: 20 }),
    issuerClassification: varchar('issuer_classification', { length: 20 }),
    formulaVersion: integer('formula_version').notNull().default(1),
    weightsVersion: integer('weights_version').notNull().default(1),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => [unique('uq_refinement_results_run_issuer').on(t.strategyRunId, t.issuerId)],
);

// ---------------------------------------------------------------------------
// AI Assistant enums + tables
// ---------------------------------------------------------------------------

export const aiModuleEnum = pgEnum('ai_module', ['ranking_explainer', 'backtest_narrator']);

export const aiReviewStatusEnum = pgEnum('review_status', [
  'pending',
  'approved',
  'rejected',
  'expired',
]);

export const confidenceLevelEnum = pgEnum('confidence_level', ['high', 'medium', 'low']);

export const explanationTypeEnum = pgEnum('explanation_type', [
  'position',
  'sector',
  'outlier',
  'metric',
]);

export const noteTypeEnum = pgEnum('note_type', [
  'summary',
  'concern',
  'highlight',
  'recommendation',
]);

export const aiSuggestions = pgTable(
  'ai_suggestions',
  {
    id: uuid('id').primaryKey(),
    tenantId: uuid('tenant_id').notNull(),
    module: aiModuleEnum('module').notNull(),
    triggerEvent: varchar('trigger_event', { length: 100 }).notNull(),
    triggerEntityId: uuid('trigger_entity_id').notNull(),
    inputHash: varchar('input_hash', { length: 64 }).notNull(),
    promptVersion: varchar('prompt_version', { length: 20 }).notNull(),
    outputSchemaVersion: varchar('output_schema_version', { length: 20 }).notNull(),
    inputSnapshot: jsonb('input_snapshot').notNull(),
    outputText: text('output_text').notNull(),
    structuredOutput: jsonb('structured_output'),
    confidence: confidenceLevelEnum('confidence').notNull(),
    modelUsed: varchar('model_used', { length: 50 }).notNull(),
    modelVersion: varchar('model_version', { length: 50 }).notNull(),
    tokensUsed: integer('tokens_used').notNull(),
    promptTokens: integer('prompt_tokens').notNull(),
    completionTokens: integer('completion_tokens').notNull(),
    costUsd: numeric('cost_usd').notNull().default('0'),
    reviewStatus: aiReviewStatusEnum('review_status').notNull().default('pending'),
    reviewedBy: uuid('reviewed_by'),
    reviewedAt: timestamp('reviewed_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => [
    unique('uq_ai_suggestions_dedup').on(t.module, t.triggerEntityId, t.inputHash, t.promptVersion),
  ],
);

export const aiExplanations = pgTable('ai_explanations', {
  id: uuid('id').primaryKey(),
  suggestionId: uuid('suggestion_id')
    .notNull()
    .references(() => aiSuggestions.id, { onDelete: 'cascade' }),
  entityType: varchar('entity_type', { length: 50 }).notNull(),
  entityId: varchar('entity_id', { length: 100 }).notNull(),
  explanationType: explanationTypeEnum('explanation_type').notNull(),
  content: text('content').notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});

export const aiResearchNotes = pgTable('ai_research_notes', {
  id: uuid('id').primaryKey(),
  suggestionId: uuid('suggestion_id')
    .notNull()
    .references(() => aiSuggestions.id, { onDelete: 'cascade' }),
  noteType: noteTypeEnum('note_type').notNull(),
  content: text('content').notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});

// ---------------------------------------------------------------------------
// Chat + Council tables
// ---------------------------------------------------------------------------

export const chatModeEnum = pgEnum('chat_mode', [
  'free_chat',
  'agent_solo',
  'roundtable',
  'debate',
  'comparison',
]);

export const chatRoleEnum = pgEnum('chat_role', [
  'user',
  'assistant',
  'system',
  'tool',
  'agent',
]);

export const agentIdEnum = pgEnum('agent_id', [
  'barsi',
  'graham',
  'greenblatt',
  'buffett',
  'moderator',
]);

export const agentVerdictEnum = pgEnum('agent_verdict', [
  'buy',
  'watch',
  'avoid',
  'insufficient_data',
]);

export const councilModeEnum = pgEnum('council_mode', [
  'solo',
  'roundtable',
  'debate',
  'comparison',
]);

export const chatSessions = pgTable('chat_sessions', {
  id: uuid('id').primaryKey(),
  tenantId: uuid('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  userId: uuid('user_id')
    .notNull()
    .references(() => users.id, { onDelete: 'cascade' }),
  title: text('title'),
  mode: chatModeEnum('mode').notNull().default('free_chat'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  archivedAt: timestamp('archived_at', { withTimezone: true }),
});

export const chatMessages = pgTable('chat_messages', {
  id: uuid('id').primaryKey(),
  sessionId: uuid('session_id')
    .notNull()
    .references(() => chatSessions.id, { onDelete: 'cascade' }),
  role: chatRoleEnum('role').notNull(),
  content: text('content').notNull(),
  agentId: varchar('agent_id', { length: 20 }),
  toolCallsJson: jsonb('tool_calls_json'),
  tokensUsed: integer('tokens_used'),
  costUsd: numeric('cost_usd'),
  providerUsed: varchar('provider_used', { length: 20 }),
  modelUsed: varchar('model_used', { length: 50 }),
  fallbackLevel: integer('fallback_level'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});

export const councilSessions = pgTable('council_sessions', {
  id: uuid('id').primaryKey(),
  chatSessionId: uuid('chat_session_id')
    .references(() => chatSessions.id, { onDelete: 'cascade' }),
  tenantId: uuid('tenant_id')
    .notNull()
    .references(() => tenants.id, { onDelete: 'cascade' }),
  mode: councilModeEnum('mode').notNull(),
  assetIds: jsonb('asset_ids').notNull(),
  agentIds: jsonb('agent_ids').notNull(),
  status: varchar('status', { length: 20 }).notNull().default('pending'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});

export const councilOpinions = pgTable('council_opinions', {
  id: uuid('id').primaryKey(),
  councilSessionId: uuid('council_session_id')
    .notNull()
    .references(() => councilSessions.id, { onDelete: 'cascade' }),
  agentId: varchar('agent_id', { length: 20 }).notNull(),
  verdict: agentVerdictEnum('verdict').notNull(),
  confidence: integer('confidence').notNull(),
  opinionJson: jsonb('opinion_json').notNull(),
  hardRejectsJson: jsonb('hard_rejects_json'),
  profileVersion: integer('profile_version').notNull().default(1),
  promptVersion: integer('prompt_version').notNull().default(1),
  providerUsed: varchar('provider_used', { length: 20 }),
  modelUsed: varchar('model_used', { length: 50 }),
  fallbackLevel: integer('fallback_level'),
  tokensUsed: integer('tokens_used'),
  costUsd: numeric('cost_usd'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});

export const councilDebates = pgTable('council_debates', {
  id: uuid('id').primaryKey(),
  councilSessionId: uuid('council_session_id')
    .notNull()
    .references(() => councilSessions.id, { onDelete: 'cascade' }),
  roundNumber: integer('round_number').notNull(),
  agentId: varchar('agent_id', { length: 20 }).notNull(),
  content: text('content').notNull(),
  targetAgentId: varchar('target_agent_id', { length: 20 }),
  providerUsed: varchar('provider_used', { length: 20 }),
  modelUsed: varchar('model_used', { length: 50 }),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});

export const councilSyntheses = pgTable('council_syntheses', {
  id: uuid('id').primaryKey(),
  councilSessionId: uuid('council_session_id')
    .notNull()
    .references(() => councilSessions.id, { onDelete: 'cascade' }),
  scoreboardJson: jsonb('scoreboard_json').notNull(),
  conflictsJson: jsonb('conflicts_json').notNull(),
  synthesisText: text('synthesis_text').notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});
