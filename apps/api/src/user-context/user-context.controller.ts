import { Body, Controller, Get, Put, UseGuards } from '@nestjs/common';
import { updateUserContextSchema } from '@q3/shared-contracts';

import { UserContextService } from './user-context.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('user-context')
@UseGuards(AuthGuard)
export class UserContextController {
  constructor(private readonly service: UserContextService) {}

  @Get()
  async get(@CurrentUser() user: JwtPayload) {
    const profile = await this.service.get(user.sub, user.tenantId);
    return profile ?? { preferredStrategy: null, watchlistJson: null, preferencesJson: null };
  }

  @Put()
  async upsert(@Body() body: unknown, @CurrentUser() user: JwtPayload) {
    const input = updateUserContextSchema.parse(body);
    return this.service.upsert(user.sub, user.tenantId, input);
  }
}
