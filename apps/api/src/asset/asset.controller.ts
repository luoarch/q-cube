import { BadRequestException, Controller, Get, Param, UseGuards } from '@nestjs/common';

import { AssetService } from './asset.service.js';
import { AuthGuard } from '../auth/auth.guard.js';
import { CurrentUser } from '../auth/current-user.decorator.js';

import type { JwtPayload } from '../auth/auth.service.js';

const TICKER_RE = /^[A-Z0-9]{3,10}$/;

@Controller('assets')
@UseGuards(AuthGuard)
export class AssetController {
  constructor(private readonly assetService: AssetService) {}

  @Get(':ticker')
  async getByTicker(@Param('ticker') ticker: string, @CurrentUser() user: JwtPayload) {
    const normalized = ticker.toUpperCase();
    if (!TICKER_RE.test(normalized)) {
      throw new BadRequestException('Invalid ticker format');
    }
    return this.assetService.getByTicker(normalized, user.tenantId);
  }
}
