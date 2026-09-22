/**
 * PR 3351 (review round 9, P1): устойчивый Idempotency-Key для создания
 * лабораторного бланка (POST /lab/report-instances).
 *
 * Round 8 закрыл UI-пути потери ответа (навигационная блокировка CREATE:
 * смена пациента/приёма, route leave, browser Back, sentinel-deferred URL
 * write), но сама операция осталась неидемпотентной: транспортный разрыв
 * ПОСЛЕ серверного commit (502 reverse proxy, crash вкладки/процесса,
 * подтверждённый beforeunload, retry после reload) оставлял frontend без
 * ID созданного бланка — оператор повторял создание и получал второй бланк.
 *
 * Backend-контракт (IdempotencyMiddleware, PR-6/#3092): любой POST с
 * заголовком Idempotency-Key координируется — ответ 2xx сохраняется в
 * кэше (in-memory + Redis distributed claim), повторный запрос с тем же
 * ключом и тем же payload получает СОХРАНЁННЫЙ ответ вместо повторного
 * исполнения хендлера. Без заголовка middleware прозрачно пропускает
 * запрос — идемпотентность opt-in.
 *
 * Ключ здесь живёт ровно один «логический клик» создания:
 *  - bind:    первой попытке генерируется UUID операции и пара
 *             (ключ, digest payload) сохраняется в sessionStorage;
 *  - proceed: попытка с неопределённым исходом (сетевая ошибка / потерянный
 *             ответ / reload до обработки ответа) НЕ очищает слот —
 *             повторный клик отправляет ТОТ ЖЕ ключ и тот же payload,
 *             backend отвечает закоммиченным бланком (exactly-once);
 *  - rotate:  digest payload изменился (пересчитался visit_id/resolution) —
 *             это ДРУГАЯ логическая операция: новый ключ, новый легитимный
 *             бланк (контракт ревью: «для нового ключа создаётся новый,
 *             легитимно отдельный бланк»);
 *  - clear:   ответ 2xx получен — исход известен, слот освобождается,
 *             следующее создание получает свежий ключ.
 *
 * Хранение — sessionStorage: переживает reload в той же вкладке (контракт
 * ревью: «ключ должен переживать неопределённый исход и повторно
 * использоваться после reload/reconcile»), не протекает в другие вкладки.
 * Слот адресован контексту операции (appointment_id, fallback patient_id):
 * неопределённый исход по пациенту A не мешает создать бланк пациенту B,
 * а возврат к A переиспользует сохранённый ключ. Перекрёстная защита
 * пользователей не нужна: кэш middleware namespaced по каноническому
 * user id — чужой ключ в чужом namespace просто исполняется заново.
 *
 * Payload-привязка — ОДНОСТОРОННИЙ digest (SHA-256 через WebCrypto,
 * детерминированный не-криптографический fallback для окружений без
 * crypto.subtle — http-контексты без secure context). CodeQL
 * js/clear-text-storage-of-sensitive-data (#1315, round 10): сериализованный
 * payload создания содержит ФЛИ (patient_id, appointment_id, клинические
 * поля) и в raw-виде в storage не хранится НИКОГДА — equality-контракт
 * proceed/rotate полностью сохраняется на digest-сравнении: тот же payload
 * → тот же digest → тот же ключ; изменившийся payload → другой digest →
 * rotate. Серверная привязка ключа к body не меняется: middleware хеширует
 * сырой body запроса, digest здесь — только локальная память «того же
 * логического клика». Формат слота меняется до первого попадания в main
 * (PR ещё draft), миграция raw-слотов не нужна.
 */

const STORAGE_PREFIX = 'lab:report-create:idempotency';

interface StoredCreateInstanceKey {
  key: string;
  payloadDigest: string;
}

function storageSlotId(appointmentKey: string): string {
  return `${STORAGE_PREFIX}:${appointmentKey}`;
}

function readStoredKey(slot: string): StoredCreateInstanceKey | null {
  try {
    const raw = window.sessionStorage.getItem(slot);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredCreateInstanceKey> | null;
    if (typeof parsed?.key !== 'string' || !parsed.key) return null;
    if (typeof parsed?.payloadDigest !== 'string' || !parsed.payloadDigest) return null;
    return { key: parsed.key, payloadDigest: parsed.payloadDigest };
  } catch {
    // Недоступный/повреждённый storage (private mode, quota) — деградация
    // к ключу на один клик: идемпотентность внутри попытки сохраняется
    // (double-submit той же попытки), reload-ретрай получает новый ключ.
    return null;
  }
}

function writeStoredKey(slot: string, record: StoredCreateInstanceKey): void {
  try {
    window.sessionStorage.setItem(slot, JSON.stringify(record));
  } catch {
    // См. readStoredKey: storage-only деградация, не ломает операцию.
  }
}

function removeStoredKey(slot: string): void {
  try {
    window.sessionStorage.removeItem(slot);
  } catch {
    // См. readStoredKey.
  }
}

/**
 * Тот же сериализатор, которым api-клиент строит тело запроса: вход digest
 * побайтово совпадает с тем, что хеширует IdempotencyMiddleware.
 */
export function serializeCreateInstancePayload(payload: Record<string, unknown>): string {
  return JSON.stringify(payload);
}

/**
 * Детерминированный не-криптографический digest для окружений без
 * crypto.subtle (http без secure context): два прохода FNV-1a с разными
 * seed (64-битное пространство коллизий) + длина входа. Равенство
 * digest-ов = равенство payload с практической точностью для локального
 * proceed/rotate-решения; даже коллизия безопасна — серверная привязка
 * ключа к body отвергнет несовпадающий payload кодом 409 (Codex R2 #3092),
 * а не создаст дубликат.
 */
function fnv1aDigest(input: string): string {
  const passes = [0x811c9dc5, 0x01000193];
  const parts = passes.map((seed) => {
    let hash = seed >>> 0;
    for (let i = 0; i < input.length; i += 1) {
      hash ^= input.charCodeAt(i);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash.toString(16).padStart(8, '0');
  });
  return `fnv1a:${parts[0]}${parts[1]}:${input.length.toString(16)}`;
}

/**
 * Односторонний digest сериализованного payload (CodeQL #1315, round 10):
 * primary — SHA-256 через WebCrypto (канонический барьер для
 * clear-text-storage), fallback — FNV-1a для не-secure контекстов.
 * Raw payload в storage не попадает ни на одном пути.
 */
async function computePayloadDigest(serializedPayload: string): Promise<string> {
  if (typeof crypto !== 'undefined' && crypto.subtle && typeof crypto.subtle.digest === 'function') {
    try {
      const bytes = new TextEncoder().encode(serializedPayload);
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      const hex = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
      return `sha256:${hex}`;
    } catch {
      // Деградация к FNV-1a (см. fnv1aDigest) — digest-контракт сохраняется.
    }
  }
  return fnv1aDigest(serializedPayload);
}

/**
 * Контекст операции-слота: appointment_id (fallback patient_id). Один
 * приём — один слот: повтор по тому же приёму переиспользует ключ,
 * другой приём имеет собственный слот и собственный жизненный цикл.
 */
export function buildCreateInstanceSlotKey(payload: Record<string, unknown>): string {
  const appointmentId = payload.appointment_id as string | number | null | undefined;
  if (appointmentId !== null && appointmentId !== undefined && appointmentId !== '') {
    return `appointment:${String(appointmentId)}`;
  }
  const patientId = payload.patient_id as string | number | null | undefined;
  if (patientId !== null && patientId !== undefined && patientId !== '') {
    return `patient:${String(patientId)}`;
  }
  return 'context:unknown';
}

/**
 * UUID операции (тот же генератор, что и cart createIdempotencyKey в
 * wizardUtils): crypto.randomUUID с fallback для окружений без WebCrypto.
 */
export function generateCreateInstanceOperationId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `lab-create-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

/**
 * Ключ для ОТПРАВКИ текущей попытки создания (bind / proceed / rotate —
 * см. контракт модуля). Побочный эффект: слот sessionStorage обновляется
 * под выбранную ветку, поэтому вызывать ровно один раз на попытку, ПОСЛЕ
 * сборки payload и ДО labReportingApi.createInstance(). Асинхронность —
 * SHA-256 digest через WebCrypto (crypto.subtle.digest асинхронен по
 * спецификации); все точки вызова уже в async-контексте.
 */
export async function resolveCreateInstanceIdempotencyKey(
  payload: Record<string, unknown>,
): Promise<string> {
  const slot = storageSlotId(buildCreateInstanceSlotKey(payload));
  const snapshot = serializeCreateInstancePayload(payload);
  const payloadDigest = await computePayloadDigest(snapshot);
  const stored = readStoredKey(slot);
  // proceed: тот же payload (тот же digest), исход прошлой попытки неизвестен
  // — тот же ключ, backend вернёт закоммиченный бланк вместо второго INSERT.
  if (stored && stored.payloadDigest === payloadDigest) {
    return stored.key;
  }
  // bind (слота нет) / rotate (payload изменился — другая логическая
  // операция): свежий ключ и свежий digest.
  const key = generateCreateInstanceOperationId();
  writeStoredKey(slot, { key, payloadDigest });
  return key;
}

/**
 * Исход операции ИЗВЕСТЕН (2xx получен и обработан): слот освобождается —
 * следующее создание того же приёма становится новой операцией с новым
 * ключом и новым легитимным бланком. Вызывается сразу после успешного
 * await createInstance (включая ветку background-reconcile: бланк
 * закоммичен и найден, повтор не нужен).
 */
export function clearCreateInstanceIdempotencyKey(payload: Record<string, unknown>): void {
  removeStoredKey(storageSlotId(buildCreateInstanceSlotKey(payload)));
}

/**
 * Интроспекция для тестов/диагностики: сохранён ли по этому контексту
 * ключ с неопределённым исходом (и каким payload-digest-ом он связан —
 * raw payload в слоте не хранится, CodeQL #1315).
 */
export function peekCreateInstanceIdempotencyKey(
  payload: Record<string, unknown>,
): StoredCreateInstanceKey | null {
  return readStoredKey(storageSlotId(buildCreateInstanceSlotKey(payload)));
}
