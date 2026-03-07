import { z } from "zod";

// Zod 4's z.string().uuid() enforces RFC 4122 version/variant bits,
// which rejects common placeholder UUIDs (e.g. 00000000-0000-0000-0000-000000000001).
// Use a permissive hex-and-dash pattern instead.
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const uuidSchema = z.string().regex(UUID_RE, "Invalid UUID");

export const runStatusSchema = z.enum(["pending", "running", "completed", "failed"]);

export const strategyTypeSchema = z.enum([
  "magic_formula_original",
  "magic_formula_brazil",
  "magic_formula_hybrid"
]);

export type RunStatus = z.infer<typeof runStatusSchema>;
export type StrategyType = z.infer<typeof strategyTypeSchema>;
