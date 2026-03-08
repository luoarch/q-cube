import { z } from 'zod';

export const dashboardKpiSchema = z.object({
  label: z.string(),
  value: z.union([z.number(), z.string()]),
  change: z.number().optional(),
  positive: z.boolean().optional(),
  format: z.string().optional(),
});

export const dashboardPipelineSchema = z.object({
  stage: z.string(),
  progress: z.number(),
  lastRun: z.string().nullable(),
});

export const dashboardTopRankedSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  rank: z.number(),
  price: z.number().nullable(),
  change: z.number().nullable(),
});

export const dashboardSectorDistSchema = z.object({
  name: z.string(),
  value: z.number(),
});

export const dashboardSummarySchema = z.object({
  kpis: z.array(dashboardKpiSchema),
  pipelineStatus: dashboardPipelineSchema,
  topRanked: z.array(dashboardTopRankedSchema),
  sectorDistribution: z.array(dashboardSectorDistSchema),
});

export type DashboardSummary = z.infer<typeof dashboardSummarySchema>;
