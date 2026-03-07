import { Module } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { JwtModule } from "@nestjs/jwt";
import type { JwtModuleOptions } from "@nestjs/jwt";
import type { EnvConfig } from "../config/env.schema.js";
import { AuthController } from "./auth.controller.js";
import { AuthService } from "./auth.service.js";
import { AuthGuard } from "./auth.guard.js";
import { RoleGuard } from "./role.guard.js";

@Module({
  imports: [
    JwtModule.registerAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService<EnvConfig>): JwtModuleOptions => {
        const expiry = config.get("JWT_EXPIRY", { infer: true })!;
        return {
          secret: config.get("JWT_SECRET", { infer: true })!,
          signOptions: { expiresIn: expiry as `${number}m` },
        };
      },
    }),
  ],
  controllers: [AuthController],
  providers: [AuthService, AuthGuard, RoleGuard],
  exports: [AuthService, AuthGuard, RoleGuard, JwtModule],
})
export class AuthModule {}
