/**
 * WebSocket message validation schemas (zod).
 *
 * Replaces `JSON.parse(event.data) as parsed message` casts with
 * runtime-validated parsing. Invalid messages are logged and dropped.
 */
import { z } from 'zod';
import logger from './logger';

/**
 * Generic WS message envelope — every message has at least a `type` field.
 */
export const WsMessageSchema = z.object({
  type: z.string(),
}).passthrough();

export type WsMessage = z.infer<typeof WsMessageSchema>;

/**
 * Parse a WebSocket message string with zod validation.
 * Returns null if parsing fails.
 */
export function parseWsMessage<T extends z.ZodTypeAny>(
  raw: string,
  schema: T
): z.infer<T> | null {
  try {
    const json = JSON.parse(raw);
    const result = schema.safeParse(json);
    if (!result.success) {
      logger.warn('[WS] Message validation failed', {
        errors: result.error.issues,
        raw: raw.slice(0, 200),
      });
      return null;
    }
    return result.data;
  } catch (err) {
    logger.warn('[WS] JSON.parse failed', { error: String(err) });
    return null;
  }
}

/**
 * Parse with the generic WsMessageSchema (type-only validation).
 * Use this when you don't need full payload validation yet.
 */
export function parseWsEvent(raw: string): WsMessage | null {
  return parseWsMessage(raw, WsMessageSchema);
}
