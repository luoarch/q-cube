import { Module } from '@nestjs/common';

import { IntelligenceController } from './intelligence.controller.js';
import { IntelligenceService } from './intelligence.service.js';
import { AssetModule } from '../asset/asset.module.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule, AssetModule],
  controllers: [IntelligenceController],
  providers: [IntelligenceService],
})
export class IntelligenceModule {}
