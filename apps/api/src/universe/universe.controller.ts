import { Controller, Get, UseGuards } from '@nestjs/common';

import { type UniverseService } from './universe.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

@Controller('universe')
@UseGuards(AuthGuard)
export class UniverseController {
  constructor(private readonly universeService: UniverseService) {}

  @Get()
  async get(@CurrentUser() _user: JwtPayload) {
    return this.universeService.getUniverse();
  }
}
