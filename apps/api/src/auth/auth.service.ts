import {
  Inject,
  Injectable,
  Logger,
  UnauthorizedException,
} from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { JwtService } from "@nestjs/jwt";
import {
  loginResponseSchema,
  refreshResponseSchema,
  authMeResponseSchema,
  type LoginRequest,
  type RefreshRequest,
} from "@q3/shared-contracts";
import * as bcrypt from "bcryptjs";
import { asc, eq } from "drizzle-orm";
import type { NodePgDatabase } from "drizzle-orm/node-postgres";
import { DB } from "../database/database.constants.js";
import { memberships, users } from "../db/schema.js";
import type * as schema from "../db/schema.js";
import type { EnvConfig } from "../config/env.schema.js";

export interface JwtPayload {
  sub: string;
  tenantId: string;
  role: string;
  type?: "access" | "refresh";
}

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);
  private readonly maxAttempts: number;
  private readonly lockoutMinutes: number;
  private readonly refreshExpiry: string;

  constructor(
    @Inject(DB) private readonly db: NodePgDatabase<typeof schema>,
    private readonly jwtService: JwtService,
    private readonly config: ConfigService<EnvConfig>,
  ) {
    this.maxAttempts = this.config.get("LOGIN_MAX_ATTEMPTS", { infer: true })!;
    this.lockoutMinutes = this.config.get("LOGIN_LOCKOUT_MINUTES", { infer: true })!;
    this.refreshExpiry = this.config.get("JWT_REFRESH_EXPIRY", { infer: true })!;
  }

  async login(input: LoginRequest) {
    const rows = await this.db
      .select({
        id: users.id,
        email: users.email,
        fullName: users.fullName,
        passwordHash: users.passwordHash,
        failedLoginAttempts: users.failedLoginAttempts,
        lockedUntil: users.lockedUntil,
        tenantId: memberships.tenantId,
        role: memberships.role,
      })
      .from(users)
      .innerJoin(memberships, eq(memberships.userId, users.id))
      .where(eq(users.email, input.email))
      .orderBy(asc(memberships.createdAt))
      .limit(1);

    const user = rows[0];

    if (!user || !user.passwordHash) {
      throw new UnauthorizedException("Invalid credentials");
    }

    if (user.lockedUntil && user.lockedUntil > new Date()) {
      throw new UnauthorizedException("Account temporarily locked. Please try again later.");
    }

    const valid = await bcrypt.compare(input.password, user.passwordHash);

    if (!valid) {
      const attempts = user.failedLoginAttempts + 1;
      const lockedUntil =
        attempts >= this.maxAttempts
          ? new Date(Date.now() + this.lockoutMinutes * 60_000)
          : null;

      await this.db
        .update(users)
        .set({
          failedLoginAttempts: attempts,
          lockedUntil,
          updatedAt: new Date(),
        })
        .where(eq(users.id, user.id));

      if (lockedUntil) {
        this.logger.warn(`Account locked for user ${user.id} after ${attempts} failed attempts`);
      }

      throw new UnauthorizedException("Invalid credentials");
    }

    // Reset failed attempts on success
    await this.db
      .update(users)
      .set({
        failedLoginAttempts: 0,
        lockedUntil: null,
        updatedAt: new Date(),
      })
      .where(eq(users.id, user.id));

    const tokenPayload: JwtPayload = {
      sub: user.id,
      tenantId: user.tenantId,
      role: user.role,
    };

    const accessToken = await this.jwtService.signAsync({
      ...tokenPayload,
      type: "access",
    });

    const refreshToken = await this.jwtService.signAsync(
      { sub: user.id, type: "refresh" },
      { expiresIn: this.refreshExpiry as `${number}d` },
    );

    return loginResponseSchema.parse({
      accessToken,
      refreshToken,
      user: {
        id: user.id,
        email: user.email,
        fullName: user.fullName,
        tenantId: user.tenantId,
        role: user.role,
      },
    });
  }

  async refreshTokens(input: RefreshRequest) {
    let payload: JwtPayload;
    try {
      payload = await this.jwtService.verifyAsync<JwtPayload>(input.refreshToken);
    } catch {
      throw new UnauthorizedException("Invalid refresh token");
    }

    if (payload.type !== "refresh") {
      throw new UnauthorizedException("Invalid token type");
    }

    // Lookup user and verify not locked
    const rows = await this.db
      .select({
        id: users.id,
        lockedUntil: users.lockedUntil,
        tenantId: memberships.tenantId,
        role: memberships.role,
      })
      .from(users)
      .innerJoin(memberships, eq(memberships.userId, users.id))
      .where(eq(users.id, payload.sub))
      .orderBy(asc(memberships.createdAt))
      .limit(1);

    const user = rows[0];
    if (!user) {
      throw new UnauthorizedException("User not found");
    }

    if (user.lockedUntil && user.lockedUntil > new Date()) {
      throw new UnauthorizedException("Account temporarily locked");
    }

    const accessToken = await this.jwtService.signAsync({
      sub: user.id,
      tenantId: user.tenantId,
      role: user.role,
      type: "access",
    });

    const refreshToken = await this.jwtService.signAsync(
      { sub: user.id, type: "refresh" },
      { expiresIn: this.refreshExpiry as `${number}d` },
    );

    return refreshResponseSchema.parse({ accessToken, refreshToken });
  }

  async getMe(userId: string) {
    const rows = await this.db
      .select({
        id: users.id,
        email: users.email,
        fullName: users.fullName,
        tenantId: memberships.tenantId,
        role: memberships.role,
      })
      .from(users)
      .innerJoin(memberships, eq(memberships.userId, users.id))
      .where(eq(users.id, userId))
      .orderBy(asc(memberships.createdAt))
      .limit(1);

    const user = rows[0];
    if (!user) {
      throw new UnauthorizedException("User not found");
    }

    return authMeResponseSchema.parse({
      id: user.id,
      email: user.email,
      fullName: user.fullName,
      tenantId: user.tenantId,
      role: user.role,
    });
  }
}
