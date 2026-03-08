import { Module } from '@nestjs/common';

import { AIController } from './ai.controller.js';
import { AIService } from './ai.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [AIController],
  providers: [AIService],
  exports: [AIService],
})
export class AIModule {}
