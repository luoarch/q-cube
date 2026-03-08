import { createParamDecorator, type ExecutionContext } from '@nestjs/common';

import type { JwtPayload } from './auth.service.js';

export const CurrentUser = createParamDecorator(
  (_data: unknown, ctx: ExecutionContext): JwtPayload => {
    const request = ctx.switchToHttp().getRequest();
    return {
      sub: request.userId,
      tenantId: request.tenantId,
      role: request.role,
    };
  },
);
