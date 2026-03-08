import { z } from 'zod';

export const analysisVersionSetSchema = z.object({
  refinerFormulaVersion: z.number(),
  refinerWeightsVersion: z.number(),
  comparisonRulesVersion: z.number(),
  councilProfileVersion: z.number(),
  councilPromptVersion: z.number(),
});

export type AnalysisVersionSet = z.infer<typeof analysisVersionSetSchema>;
