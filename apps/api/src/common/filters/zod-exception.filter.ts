import {
  type ArgumentsHost,
  Catch,
  type ExceptionFilter,
  HttpStatus,
  Logger
} from "@nestjs/common";
import type { Response } from "express";
import { ZodError } from "zod";

@Catch(ZodError)
export class ZodExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(ZodExceptionFilter.name);

  catch(exception: ZodError, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();

    this.logger.warn(`Validation failed: ${exception.message}`);

    response.status(HttpStatus.BAD_REQUEST).json({
      statusCode: HttpStatus.BAD_REQUEST,
      message: "Validation failed",
      errors: exception.issues.map((issue) => ({
        path: issue.path,
        message: issue.message
      }))
    });
  }
}
