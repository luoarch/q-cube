import { z } from "zod";

export const rankingItemSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  sector: z.string(),
  magicFormulaRank: z.number(),
  earningsYield: z.number(),
  returnOnCapital: z.number(),
  marketCap: z.number(),
  price: z.number().nullable(),
  change: z.number().nullable(),
  quality: z.enum(["high", "medium", "low"]),
  liquidity: z.enum(["high", "medium", "low"]),
});

export const paginationMetaSchema = z.object({
  page: z.number(),
  limit: z.number(),
  total: z.number(),
  totalPages: z.number(),
});

export const paginatedRankingSchema = z.object({
  data: z.array(rankingItemSchema),
  meta: paginationMetaSchema,
});

export type RankingItem = z.infer<typeof rankingItemSchema>;
export type PaginationMeta = z.infer<typeof paginationMetaSchema>;
export type PaginatedRanking = z.infer<typeof paginatedRankingSchema>;
