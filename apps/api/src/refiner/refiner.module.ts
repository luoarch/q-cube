import { Module } from '@nestjs/common';

import { RefinerController } from './refiner.controller.js';
import { RefinerService } from './refiner.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [RefinerController],
  providers: [RefinerService],
  exports: [RefinerService],
})
export class RefinerModule {}
