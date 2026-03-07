import { Body, Controller, Get, Post, UseGuards } from "@nestjs/common";
import { Throttle } from "@nestjs/throttler";
import { loginRequestSchema, refreshRequestSchema } from "@q3/shared-contracts";
import { AuthService, type JwtPayload } from "./auth.service.js";
import { AuthGuard } from "./auth.guard.js";
import { CurrentUser } from "./current-user.decorator.js";

@Controller("auth")
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post("login")
  @Throttle({ default: { ttl: 60_000, limit: 5 } })
  async login(@Body() body: unknown) {
    const input = loginRequestSchema.parse(body);
    return this.authService.login(input);
  }

  @Post("refresh")
  @Throttle({ default: { ttl: 60_000, limit: 10 } })
  async refresh(@Body() body: unknown) {
    const input = refreshRequestSchema.parse(body);
    return this.authService.refreshTokens(input);
  }

  @Get("me")
  @UseGuards(AuthGuard)
  async me(@CurrentUser() user: JwtPayload) {
    return this.authService.getMe(user.sub);
  }
}
