import {
  Injectable,
  UnauthorizedException,
} from "@nestjs/common";
import type { CanActivate, ExecutionContext } from "@nestjs/common";
import { JwtService } from "@nestjs/jwt";
import type { Request } from "express";
import type { JwtPayload } from "./auth.service.js";

@Injectable()
export class AuthGuard implements CanActivate {
  constructor(private readonly jwtService: JwtService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest<Request>();
    const header = request.headers.authorization;

    if (!header?.startsWith("Bearer ")) {
      throw new UnauthorizedException("Missing authorization header");
    }

    const token = header.slice(7);

    let payload: JwtPayload;
    try {
      payload = await this.jwtService.verifyAsync<JwtPayload>(token);
    } catch {
      throw new UnauthorizedException("Invalid or expired token");
    }

    if (payload.type === "refresh") {
      throw new UnauthorizedException("Refresh tokens cannot be used for authentication");
    }

    (request as any).userId = payload.sub;
    (request as any).tenantId = payload.tenantId;
    (request as any).role = payload.role;

    return true;
  }
}
