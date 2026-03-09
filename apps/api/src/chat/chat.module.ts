import { Module } from '@nestjs/common';

import { ChatController } from './chat.controller.js';
import { ChatService } from './chat.service.js';
import { CouncilService } from './council.service.js';
import { AuthModule } from '../auth/auth.module.js';

@Module({
  imports: [AuthModule],
  controllers: [ChatController],
  providers: [ChatService, CouncilService],
  exports: [ChatService, CouncilService],
})
export class ChatModule {}
