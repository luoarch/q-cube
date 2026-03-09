import { Module } from '@nestjs/common';

import { UserContextController } from './user-context.controller.js';
import { UserContextService } from './user-context.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [UserContextController],
  providers: [UserContextService],
  exports: [UserContextService],
})
export class UserContextModule {}
