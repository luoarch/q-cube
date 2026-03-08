import * as bcrypt from 'bcryptjs';
import { eq } from 'drizzle-orm';
import { drizzle } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';

import { users, tenants, memberships } from '../db/schema.js';

const DATABASE_URL = process.env.DATABASE_URL ?? 'postgresql://127.0.0.1:5432/q3';
const DEMO_TENANT_ID = '00000000-0000-0000-0000-000000000001';
const DEMO_USER_ID = '00000000-0000-0000-0000-000000000010';
const DEMO_MEMBERSHIP_ID = '00000000-0000-0000-0000-000000000011';

async function main() {
  const pool = new Pool({ connectionString: DATABASE_URL });
  const db = drizzle(pool);

  const passwordHash = await bcrypt.hash('Q3demo!2026', 12);
  console.log('Password hashed with bcrypt cost 12');

  // Upsert tenant
  const existingTenant = await db
    .select()
    .from(tenants)
    .where(eq(tenants.id, DEMO_TENANT_ID))
    .limit(1);

  if (existingTenant.length === 0) {
    await db.insert(tenants).values({
      id: DEMO_TENANT_ID,
      name: 'Demo Tenant',
    });
    console.log('Created demo tenant');
  } else {
    console.log('Demo tenant already exists');
  }

  // Upsert user
  const existingUser = await db.select().from(users).where(eq(users.email, 'demo@q3.dev')).limit(1);

  if (existingUser.length === 0) {
    await db.insert(users).values({
      id: DEMO_USER_ID,
      email: 'demo@q3.dev',
      fullName: 'Demo User',
      passwordHash,
    });
    console.log('Created demo user: demo@q3.dev');
  } else {
    await db
      .update(users)
      .set({ passwordHash, updatedAt: new Date() })
      .where(eq(users.email, 'demo@q3.dev'));
    console.log('Updated demo user password hash');
  }

  // Upsert membership
  const existingMembership = await db
    .select()
    .from(memberships)
    .where(eq(memberships.userId, existingUser[0]?.id ?? DEMO_USER_ID))
    .limit(1);

  if (existingMembership.length === 0) {
    await db.insert(memberships).values({
      id: DEMO_MEMBERSHIP_ID,
      tenantId: DEMO_TENANT_ID,
      userId: existingUser[0]?.id ?? DEMO_USER_ID,
      role: 'owner',
    });
    console.log('Created demo membership (owner)');
  } else {
    console.log('Demo membership already exists');
  }

  await pool.end();
  console.log('Done!');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
