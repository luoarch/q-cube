import { z } from "zod";

export const issuerSchema = z.object({
  id: z.string().uuid(),
  cvmCode: z.string(),
  legalName: z.string(),
  tradeName: z.string().nullable(),
  cnpj: z.string(),
  sector: z.string().nullable(),
  subsector: z.string().nullable(),
  segment: z.string().nullable(),
  status: z.string(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});

export const securitySchema = z.object({
  id: z.string().uuid(),
  issuerId: z.string().uuid(),
  ticker: z.string(),
  securityClass: z.string().nullable(),
  isPrimary: z.boolean(),
  validFrom: z.string().datetime(),
  validTo: z.string().datetime().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});

export type Issuer = z.infer<typeof issuerSchema>;
export type Security = z.infer<typeof securitySchema>;
