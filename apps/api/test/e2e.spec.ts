/**
 * E2E Integration Tests for Q³ API
 *
 * Requires real PostgreSQL + Redis (from docker-compose or local dev).
 * Set TEST_DATABASE_URL to use a separate test database.
 *
 * Tests the full deterministic pipeline:
 *   health → auth → refiner → comparison → chat CRUD
 *
 * Skips LLM-dependent endpoints (council analyze) unless AI assistant is running.
 *
 * Run: pnpm --filter @q3/api test:e2e
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';

// Load .env into process.env before NestJS ConfigModule boots
const envPath = resolve(import.meta.dirname, '..', '.env');
try {
  const envContent = readFileSync(envPath, 'utf-8');
  for (const line of envContent.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx);
    const val = trimmed.slice(eqIdx + 1);
    if (!process.env[key]) {
      process.env[key] = val;
    }
  }
} catch {
  // .env file is optional — env vars may come from shell
}

import { type INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { sql } from 'drizzle-orm';
import { type NodePgDatabase } from 'drizzle-orm/node-postgres';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { AppModule } from '../src/app.module.js';
import { DB } from '../src/database/database.constants.js';
import * as schema from '../src/db/schema.js';

// ---------------------------------------------------------------------------
// Test Data IDs (stable UUIDs for reproducibility)
// ---------------------------------------------------------------------------

const TENANT_ID = '00000000-0000-0000-0000-000000000001';
const USER_ID = '00000000-0000-0000-0000-000000000002';
const ISSUER_A_ID = '00000000-0000-0000-0000-000000000010';
const ISSUER_B_ID = '00000000-0000-0000-0000-000000000011';
const SECURITY_A_ID = '00000000-0000-0000-0000-000000000020';
const SECURITY_B_ID = '00000000-0000-0000-0000-000000000021';
const STRATEGY_RUN_ID = '00000000-0000-0000-0000-000000000030';
const REFINER_A_ID = '00000000-0000-0000-0000-000000000040';
const REFINER_B_ID = '00000000-0000-0000-0000-000000000041';

let app: INestApplication;
let db: NodePgDatabase<typeof schema>;
let authToken: string;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function request(
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<{ status: number; body: unknown }> {
  const url = await app.getUrl();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const res = await fetch(`${url}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    json = text;
  }

  return { status: res.status, body: json };
}

function get(path: string) {
  return request('GET', path);
}

function post(path: string, body?: unknown) {
  return request('POST', path, body);
}

function patch(path: string, body?: unknown) {
  return request('PATCH', path, body);
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

beforeAll(async () => {
  // Use TEST_DATABASE_URL if available, otherwise default dev DB
  if (process.env['TEST_DATABASE_URL']) {
    process.env['DATABASE_URL'] = process.env['TEST_DATABASE_URL'];
  }

  // Ensure JWT_SECRET is set
  if (!process.env['JWT_SECRET']) {
    process.env['JWT_SECRET'] = 'e2e-test-secret-must-be-at-least-32-chars-long!!';
  }

  const moduleRef = await Test.createTestingModule({
    imports: [AppModule],
  }).compile();

  app = moduleRef.createNestApplication();
  await app.init();
  await app.listen(0); // random port

  db = moduleRef.get<NodePgDatabase<typeof schema>>(DB);

  // Seed test data
  await seedTestData();

  // Generate a JWT token for the test user
  const { JwtService } = await import('@nestjs/jwt');
  const jwtService = moduleRef.get(JwtService);
  authToken = await jwtService.signAsync({
    sub: USER_ID,
    tenantId: TENANT_ID,
    role: 'admin',
    type: 'access',
  });
}, 30_000);

afterAll(async () => {
  if (db) {
    await cleanupTestData();
  }
  if (app) {
    await app.close();
  }
});

async function seedTestData() {
  // Tenant — use raw SQL to avoid Drizzle including columns not yet in DB
  await db.execute(sql`
    INSERT INTO tenants (id, name) VALUES (${TENANT_ID}, 'E2E Test Tenant')
    ON CONFLICT DO NOTHING
  `);

  // User
  await db.insert(schema.users).values({
    id: USER_ID,
    email: `e2e-${Date.now()}@test.local`,
    fullName: 'E2E Test User',
    passwordHash: '$2b$10$fakehash', // won't use login endpoint
  }).onConflictDoNothing();

  // Membership
  await db.insert(schema.memberships).values({
    id: randomUUID(),
    userId: USER_ID,
    tenantId: TENANT_ID,
    role: 'admin',
  }).onConflictDoNothing();

  // Issuers — cvmCode is required + unique
  await db.insert(schema.issuers).values([
    {
      id: ISSUER_A_ID,
      cvmCode: 'E2E_WEG_00001',
      legalName: 'WEG SA',
      tradeName: 'WEG',
      cnpj: '84429695000199',
      sector: 'Bens Industriais',
      subsector: 'Maquinas e Equipamentos',
    },
    {
      id: ISSUER_B_ID,
      cvmCode: 'E2E_RENT_00002',
      legalName: 'LOCALIZA RENT A CAR SA',
      tradeName: 'Localiza',
      cnpj: '16670085000199',
      sector: 'Consumo Ciclico',
      subsector: 'Aluguel de Carros',
    },
  ]).onConflictDoNothing();

  // Securities — validFrom is required; leave validTo null for comparison service
  await db.insert(schema.securities).values([
    { id: SECURITY_A_ID, issuerId: ISSUER_A_ID, ticker: 'WEGE3', isPrimary: true, validFrom: '2020-01-01' },
    { id: SECURITY_B_ID, issuerId: ISSUER_B_ID, ticker: 'RENT3', isPrimary: true, validFrom: '2020-01-01' },
  ]).onConflictDoNothing();

  // Computed Metrics — inputsSnapshotJson + sourceFilingIdsJson are required
  const metricPairs: Array<{
    issuerId: string;
    metricCode: string;
    value: string;
    periodType: 'annual' | 'quarterly';
    referenceDate: string;
  }> = [
    { issuerId: ISSUER_A_ID, metricCode: 'earnings_yield', value: '0.05', periodType: 'annual', referenceDate: '2024-12-31' },
    { issuerId: ISSUER_A_ID, metricCode: 'roic', value: '0.28', periodType: 'annual', referenceDate: '2024-12-31' },
    { issuerId: ISSUER_A_ID, metricCode: 'roe', value: '0.25', periodType: 'annual', referenceDate: '2024-12-31' },
    { issuerId: ISSUER_A_ID, metricCode: 'gross_margin', value: '0.35', periodType: 'annual', referenceDate: '2024-12-31' },
    { issuerId: ISSUER_A_ID, metricCode: 'debt_to_ebitda', value: '0.8', periodType: 'annual', referenceDate: '2024-12-31' },
    { issuerId: ISSUER_B_ID, metricCode: 'earnings_yield', value: '0.08', periodType: 'annual', referenceDate: '2024-12-31' },
    { issuerId: ISSUER_B_ID, metricCode: 'roic', value: '0.18', periodType: 'annual', referenceDate: '2024-12-31' },
    { issuerId: ISSUER_B_ID, metricCode: 'roe', value: '0.15', periodType: 'annual', referenceDate: '2024-12-31' },
    { issuerId: ISSUER_B_ID, metricCode: 'gross_margin', value: '0.28', periodType: 'annual', referenceDate: '2024-12-31' },
    { issuerId: ISSUER_B_ID, metricCode: 'debt_to_ebitda', value: '3.2', periodType: 'annual', referenceDate: '2024-12-31' },
  ];

  for (const m of metricPairs) {
    await db.insert(schema.computedMetrics).values({
      id: randomUUID(),
      issuerId: m.issuerId,
      metricCode: m.metricCode,
      value: m.value,
      periodType: m.periodType,
      referenceDate: m.referenceDate,
      inputsSnapshotJson: {},
      sourceFilingIdsJson: [],
    }).onConflictDoNothing();
  }

  // Strategy Run — column is `strategy` not `strategyType`
  await db.insert(schema.strategyRuns).values({
    id: STRATEGY_RUN_ID,
    tenantId: TENANT_ID,
    strategy: 'magic_formula_brazil',
    status: 'completed',
    resultJson: JSON.stringify([
      { rank: 1, ticker: 'WEGE3', issuerId: ISSUER_A_ID, earningsYield: 0.05, returnOnCapital: 0.28 },
      { rank: 2, ticker: 'RENT3', issuerId: ISSUER_B_ID, earningsYield: 0.08, returnOnCapital: 0.18 },
    ]),
  }).onConflictDoNothing();

  // Refinement Results
  await db.insert(schema.refinementResults).values([
    {
      id: REFINER_A_ID,
      strategyRunId: STRATEGY_RUN_ID,
      tenantId: TENANT_ID,
      issuerId: ISSUER_A_ID,
      ticker: 'WEGE3',
      baseRank: 1,
      earningsQualityScore: '0.85',
      safetyScore: '0.90',
      operatingConsistencyScore: '0.88',
      capitalDisciplineScore: '0.80',
      refinementScore: '0.8575',
      adjustedScore: '0.92',
      adjustedRank: 1,
      flagsJson: { red: [], strength: ['strong_cash_conversion', 'ebit_growing'] },
      trendDataJson: {},
      scoringDetailsJson: {},
      dataCompletenessJson: { periodsAvailable: 3, metricsAvailable: 18, metricsExpected: 20, completenessRatio: 0.9, missingCritical: [], proxyUsed: [] },
      scoreReliability: 'high',
      issuerClassification: 'non_financial',
      formulaVersion: 1,
      weightsVersion: 1,
    },
    {
      id: REFINER_B_ID,
      strategyRunId: STRATEGY_RUN_ID,
      tenantId: TENANT_ID,
      issuerId: ISSUER_B_ID,
      ticker: 'RENT3',
      baseRank: 2,
      earningsQualityScore: '0.70',
      safetyScore: '0.60',
      operatingConsistencyScore: '0.65',
      capitalDisciplineScore: '0.55',
      refinementScore: '0.625',
      adjustedScore: '0.80',
      adjustedRank: 2,
      flagsJson: { red: ['leverage_rising'], strength: [] },
      trendDataJson: {},
      scoringDetailsJson: {},
      dataCompletenessJson: { periodsAvailable: 3, metricsAvailable: 15, metricsExpected: 20, completenessRatio: 0.75, missingCritical: ['cash_conversion'], proxyUsed: [] },
      scoreReliability: 'medium',
      issuerClassification: 'non_financial',
      formulaVersion: 1,
      weightsVersion: 1,
    },
  ]).onConflictDoNothing();
}

async function cleanupTestData() {
  // Clean up in reverse dependency order — use raw SQL for robustness
  try {
    await db.execute(sql`DELETE FROM refinement_results WHERE tenant_id = ${TENANT_ID}`);
    await db.execute(sql`DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE tenant_id = ${TENANT_ID})`);
    await db.execute(sql`DELETE FROM chat_sessions WHERE tenant_id = ${TENANT_ID}`);
    await db.execute(sql`DELETE FROM strategy_runs WHERE tenant_id = ${TENANT_ID}`);
    await db.execute(sql`DELETE FROM computed_metrics WHERE issuer_id IN (${ISSUER_A_ID}, ${ISSUER_B_ID})`);
    await db.execute(sql`DELETE FROM securities WHERE issuer_id IN (${ISSUER_A_ID}, ${ISSUER_B_ID})`);
    await db.execute(sql`DELETE FROM issuers WHERE id IN (${ISSUER_A_ID}, ${ISSUER_B_ID})`);
    await db.execute(sql`DELETE FROM memberships WHERE tenant_id = ${TENANT_ID}`);
    await db.execute(sql`DELETE FROM users WHERE id = ${USER_ID}`);
    await db.execute(sql`DELETE FROM tenants WHERE id = ${TENANT_ID}`);
  } catch (err) {
    // Best-effort cleanup — don't fail tests
    console.warn('Cleanup warning:', err);
  }
}

// ===========================================================================
// Tests
// ===========================================================================

describe('Health', () => {
  it('GET /health returns health check response', async () => {
    const res = await get('/health');
    // May be 200 or 503 depending on which services are running
    expect([200, 503]).toContain(res.status);
    const body = res.body as Record<string, unknown>;
    expect(body.status).toBeDefined();
    // Database and Redis should be up at minimum
    const details = body.details as Record<string, { status: string }>;
    expect(details.database.status).toBe('up');
    expect(details.redis.status).toBe('up');
  });
});

describe('Auth', () => {
  it('rejects unauthenticated requests', async () => {
    const saved = authToken;
    authToken = '';
    const res = await get('/ranking');
    authToken = saved;
    expect(res.status).toBe(401);
  });

  it('accepts valid JWT', async () => {
    const res = await get('/ranking');
    // May return 200 or empty array depending on data, but not 401
    expect(res.status).not.toBe(401);
  });
});

describe('Refiner', () => {
  it('GET /refiner/:strategyRunId returns refinement results', async () => {
    const res = await get(`/refiner/${STRATEGY_RUN_ID}`);
    expect(res.status).toBe(200);
    const body = res.body as Record<string, unknown>;
    expect(body.strategyRunId).toBe(STRATEGY_RUN_ID);
    expect(body.formulaVersion).toBe(1);
    expect(body.weightsVersion).toBe(1);
    expect(Array.isArray(body.results)).toBe(true);
    const results = body.results as Array<Record<string, unknown>>;
    expect(results.length).toBe(2);
    // Ordered by adjustedRank
    expect(results[0]!.ticker).toBe('WEGE3');
    expect(results[0]!.adjustedRank).toBe(1);
    expect(results[1]!.ticker).toBe('RENT3');
    expect(results[1]!.adjustedRank).toBe(2);
  });

  it('GET /refiner/:runId/:ticker returns single result', async () => {
    const res = await get(`/refiner/${STRATEGY_RUN_ID}/WEGE3`);
    expect(res.status).toBe(200);
    const body = res.body as Record<string, unknown>;
    expect(body.ticker).toBe('WEGE3');
    expect(body.earningsQualityScore).toBe(0.85);
    expect(body.scoreReliability).toBe('high');
    expect(body.flags).toEqual({ red: [], strength: ['strong_cash_conversion', 'ebit_growing'] });
  });

  it('GET /refiner/:runId/UNKNOWN returns 404', async () => {
    const res = await get(`/refiner/${STRATEGY_RUN_ID}/UNKNOWN`);
    expect(res.status).toBe(404);
  });

  it('GET /refiner/:randomId returns empty for unknown run', async () => {
    const res = await get(`/refiner/${randomUUID()}`);
    expect(res.status).toBe(200);
    const body = res.body as Record<string, unknown>;
    expect((body.results as unknown[]).length).toBe(0);
  });
});

describe('Comparison', () => {
  it('GET /compare?tickers=WEGE3,RENT3 returns comparison matrix', async () => {
    const res = await get('/compare?tickers=WEGE3,RENT3');
    expect(res.status).toBe(200);
    const body = res.body as Record<string, unknown>;
    expect(body.rulesVersion).toBe(1);
    expect(Array.isArray(body.tickers)).toBe(true);
    const tickers = body.tickers as string[];
    expect(tickers).toContain('WEGE3');
    expect(tickers).toContain('RENT3');
    expect(Array.isArray(body.metrics)).toBe(true);
    expect(Array.isArray(body.summaries)).toBe(true);
    const summaries = body.summaries as Array<Record<string, unknown>>;
    expect(summaries.length).toBeGreaterThanOrEqual(2);
    expect(Array.isArray(body.metrics)).toBe(true);
    const metrics = body.metrics as Array<Record<string, unknown>>;
    // Should have entries for standard comparison rules
    expect(metrics.length).toBeGreaterThan(0);
    const roicMetric = metrics.find((m) => m.metric === 'roic');
    expect(roicMetric).toBeDefined();
  });

  it('rejects single ticker', async () => {
    const res = await get('/compare?tickers=WEGE3');
    expect(res.status).toBe(400);
  });

  it('rejects missing tickers param', async () => {
    const res = await get('/compare');
    expect(res.status).toBe(400);
  });
});

describe('Chat CRUD', () => {
  let sessionId: string;

  it('POST /chat/sessions creates a session', async () => {
    const res = await post('/chat/sessions', {
      title: 'E2E Test Chat',
      mode: 'free_chat',
    });
    expect(res.status).toBe(201);
    const body = res.body as Record<string, unknown>;
    expect(body.id).toBeDefined();
    expect(body.title).toBe('E2E Test Chat');
    expect(body.mode).toBe('free_chat');
    sessionId = body.id as string;
  });

  it('GET /chat/sessions lists sessions', async () => {
    const res = await get('/chat/sessions');
    expect(res.status).toBe(200);
    const body = res.body as Array<Record<string, unknown>>;
    expect(Array.isArray(body)).toBe(true);
    const found = body.find((s) => s.id === sessionId);
    expect(found).toBeDefined();
  });

  it('GET /chat/sessions/:id/messages returns empty for new session', async () => {
    const res = await get(`/chat/sessions/${sessionId}/messages`);
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect((res.body as unknown[]).length).toBe(0);
  });

  it('PATCH /chat/sessions/:id/archive archives session', async () => {
    const res = await patch(`/chat/sessions/${sessionId}/archive`);
    expect(res.status).toBe(200);
    const body = res.body as Record<string, unknown>;
    expect(body.archivedAt).toBeTruthy();
  });

  it('archived session not in default list', async () => {
    const res = await get('/chat/sessions');
    const body = res.body as Array<Record<string, unknown>>;
    const found = body.find((s) => s.id === sessionId);
    expect(found).toBeUndefined();
  });
});
