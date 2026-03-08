import { z } from 'zod';

import { uuidSchema } from './_shared.js';
import { scoreReliabilitySchema } from './refiner.js';

// --- Agent verdicts & opinions ---

export const agentVerdictSchema = z.enum(['buy', 'watch', 'avoid', 'insufficient_data']);
export type AgentVerdict = z.infer<typeof agentVerdictSchema>;

export const agentIdSchema = z.enum(['barsi', 'graham', 'greenblatt', 'buffett', 'moderator']);
export type AgentId = z.infer<typeof agentIdSchema>;

export const agentOpinionSchema = z.object({
  agentId: agentIdSchema,
  profileVersion: z.number(),
  promptVersion: z.number(),
  verdict: agentVerdictSchema,
  confidence: z.number().min(0).max(100),
  dataReliability: scoreReliabilitySchema,
  thesis: z.string(),
  reasonsFor: z.array(z.string()),
  reasonsAgainst: z.array(z.string()),
  keyMetricsUsed: z.array(z.string()),
  hardRejectsTriggered: z.array(z.string()),
  unknowns: z.array(z.string()),
  whatWouldChangeMyMind: z.array(z.string()),
  investorFit: z.array(z.string()),
});
export type AgentOpinion = z.infer<typeof agentOpinionSchema>;

// --- Council scoreboard ---

export const councilScoreboardEntrySchema = z.object({
  agentId: agentIdSchema,
  verdict: agentVerdictSchema,
  confidence: z.number(),
});

export const councilScoreboardSchema = z.object({
  entries: z.array(councilScoreboardEntrySchema),
  consensus: agentVerdictSchema.nullable(),
  consensusStrength: z.number().nullable(),
});
export type CouncilScoreboard = z.infer<typeof councilScoreboardSchema>;

// --- Conflict matrix ---

export const conflictEntrySchema = z.object({
  agent1: agentIdSchema,
  agent2: agentIdSchema,
  topic: z.string(),
  agent1Position: z.string(),
  agent2Position: z.string(),
});
export type ConflictEntry = z.infer<typeof conflictEntrySchema>;

// --- Moderator synthesis ---

export const moderatorSynthesisSchema = z.object({
  convergences: z.array(z.string()),
  divergences: z.array(z.string()),
  biggestRisk: z.string(),
  entryConditions: z.array(z.string()),
  exitConditions: z.array(z.string()),
  overallAssessment: z.string(),
});
export type ModeratorSynthesis = z.infer<typeof moderatorSynthesisSchema>;

// --- Debate ---

export const debateRoundSchema = z.object({
  roundNumber: z.number().min(1).max(4),
  agentId: agentIdSchema,
  content: z.string(),
  targetAgentId: agentIdSchema.nullable(),
  timestamp: z.string(),
});
export type DebateRound = z.infer<typeof debateRoundSchema>;

// --- Audit trail ---

export const auditTrailSchema = z.object({
  inputHash: z.string(),
  promptVersions: z.record(agentIdSchema, z.number()),
  profileVersions: z.record(agentIdSchema, z.number()),
  modelsUsed: z.record(agentIdSchema, z.string()),
  providersUsed: z.record(agentIdSchema, z.string()),
  fallbackLevels: z.record(agentIdSchema, z.number()),
  totalTokens: z.number(),
  totalCostUsd: z.number(),
  totalLatencyMs: z.number(),
});
export type AuditTrail = z.infer<typeof auditTrailSchema>;

// --- Council session modes ---

export const councilModeSchema = z.enum(['solo', 'roundtable', 'debate', 'comparison']);
export type CouncilMode = z.infer<typeof councilModeSchema>;

// --- Council result ---

export const councilResultSchema = z.object({
  sessionId: uuidSchema,
  mode: councilModeSchema,
  assetIds: z.array(z.string()),
  opinions: z.array(agentOpinionSchema),
  scoreboard: councilScoreboardSchema,
  conflictMatrix: z.array(conflictEntrySchema),
  moderatorSynthesis: moderatorSynthesisSchema,
  debateLog: z.array(debateRoundSchema).optional(),
  disclaimer: z.string(),
  auditTrail: auditTrailSchema,
});
export type CouncilResult = z.infer<typeof councilResultSchema>;

// --- Disclaimer ---

export const COUNCIL_DISCLAIMER =
  'Este conteudo e meramente educacional e analitico, nao constituindo recomendacao de investimento personalizada. ' +
  'Os agentes sao inspirados em filosofias de investimento e nao representam pessoas reais. ' +
  'Consulte um profissional certificado antes de tomar decisoes de investimento. ' +
  'Produto posicionado como ferramenta analitica/educacional conforme CVM 20, CVM 178 e ANBIMA.';
