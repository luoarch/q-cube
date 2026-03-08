import { Module } from '@nestjs/common';

import { AssetController } from './asset.controller.js';
import { AssetService } from './asset.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [AssetController],
  providers: [AssetService],
})
export class AssetModule {}
