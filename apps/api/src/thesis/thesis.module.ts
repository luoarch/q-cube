import { Module } from '@nestjs/common';

import { ThesisController } from './thesis.controller.js';
import { ThesisService } from './thesis.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [ThesisController],
  providers: [ThesisService],
  exports: [ThesisService],
})
export class ThesisModule {}
