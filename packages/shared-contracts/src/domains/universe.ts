import { z } from 'zod';

export const universeSectorChildSchema = z.object({
  name: z.string(),
  count: z.number(),
  marketCap: z.number(),
});

export const universeSectorSchema = z.object({
  name: z.string(),
  count: z.number(),
  marketCap: z.number(),
  children: z.array(universeSectorChildSchema).optional(),
});

export const universeSchema = z.object({
  totalStocks: z.number(),
  sectors: z.array(universeSectorSchema),
});

export type UniverseData = z.infer<typeof universeSchema>;
