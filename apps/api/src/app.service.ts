import { Injectable } from "@nestjs/common";

@Injectable()
export class AppService {
  health() {
    return {
      service: "q3-api",
      status: "ok",
      timestamp: new Date().toISOString()
    };
  }
}
