import { Module } from '@nestjs/common';

import { ComparisonController } from './comparison.controller.js';
import { ComparisonService } from './comparison.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [ComparisonController],
  providers: [ComparisonService],
  exports: [ComparisonService],
})
export class ComparisonModule {}
