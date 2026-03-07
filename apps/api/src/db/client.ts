import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema.js";

const connectionString =
  process.env.DATABASE_URL ?? "postgresql://127.0.0.1:5432/q3";

export const pool = new Pool({ connectionString });

export const db = drizzle(pool, { schema });
