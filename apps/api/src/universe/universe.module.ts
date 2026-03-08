import { Module } from '@nestjs/common';

import { UniverseController } from './universe.controller.js';
import { UniverseService } from './universe.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [UniverseController],
  providers: [UniverseService],
})
export class UniverseModule {}
