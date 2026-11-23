/**
 * AUTH-FE-001 (audit 3886): единый толерантный парсер JWT-клеймов для
 * UI-уровня (только чтение `exp`/публичных клеймов; криптографическую
 * верификацию выполняет сервер — клиентский decode НЕ является проверкой
 * подписи).
 *
 * Проблема: JWT payload — Base64URL (`-` и `_` легальны), а «сырой»
 * `atob`reject-ит эти символы (`InvalidCharacterError`). Все три читателя
 * срока действия (useSessionTimeoutWarning.getTokenExpiryMs,
 * api/client.isTokenExpiringSoon, tokenManager.isTokenValid) падали на
 * валидных токенах с URL-safe символами: предупреждение молча skip-алось,
 * проактивный refresh не выполнялся, а isTokenValid на ошибке decode
 * возвращал TRUE (fail-open на UI-уровне).
 *
 * Решение: нормализация Base64URL → Base64 (+/, padding), decode через
 * atob, UTF-8 через TextDecoder, строгая JSON-схема. Ошибка декода —
 * null; потребитель решает политику (isTokenValid — fail-closed).
 */

const JWT_PARTS = 3;

function base64UrlToBytes(segment: string): Uint8Array {
  const normalized = segment
    .replace(/-/g, '+')
    .replace(/_/g, '/')
    .padEnd(Math.ceil(segment.length / 4) * 4, '=');
  const binary = atob(normalized);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * Декодирует payload JWT (частей === 3) в объект клеймов.
 * Возвращает null для не-JWT, пустых/битых сегментов, негодного
 * Base64URL или JSON-не-объекта. Никогда не бросает.
 */
export function decodeJwtClaims(token: string | null | undefined): Record<string, unknown> | null {
  if (typeof token !== 'string' || token.length === 0) return null;
  const parts = token.split('.');
  if (parts.length !== JWT_PARTS) return null;
  const payloadSegment = parts[1];
  if (payloadSegment.length === 0) return null;
  try {
    const json = new TextDecoder().decode(base64UrlToBytes(payloadSegment));
    const parsed: unknown = JSON.parse(json);
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Числовое поле клейма (exp и т.п.); null — отсутствует или не число. */
export function numericClaim(claims: Record<string, unknown> | null, key: string): number | null {
  if (claims === null) return null;
  const value = claims[key];
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}
