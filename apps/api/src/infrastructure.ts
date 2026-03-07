import { Redis } from "ioredis";
import { db, pool } from "./db/client.js";

const redisUrl = process.env.REDIS_URL ?? "redis://127.0.0.1:6379";

export const redis = new Redis(redisUrl, {
  maxRetriesPerRequest: 2,
  lazyConnect: true
});

export const STRATEGY_QUEUE_KEY = "q3:strategy:jobs";

export { db, pool };
