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
 *             (ключ, снимок payload) сохраняется в sessionStorage;
 *  - proceed: попытка с неопределённым исходом (сетевая ошибка / потерянный
 *             ответ / reload до обработки ответа) НЕ очищает слот —
 *             повторный клик отправляет ТОТ ЖЕ ключ и тот же payload,
 *             backend отвечает закоммиченным бланком (exactly-once);
 *  - rotate:  снимок payload изменился (пересчитался visit_id/resolution) —
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
 * Payload-привязка зеркалит серверную: middleware хеширует сырой body,
 * а serializeCreateInstancePayload() — это тот же JSON.stringify, которым
 * api-клиент строит body (стабильный порядок ключей объектного литерала).
 */

const STORAGE_PREFIX = 'lab:report-create:idempotency';

interface StoredCreateInstanceKey {
  key: string;
  payload: string;
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
    if (typeof parsed?.payload !== 'string') return null;
    return { key: parsed.key, payload: parsed.payload };
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
 * Тот же сериализатор, которым api-клиент строит тело запроса: снимок
 * payload побайтово совпадает с тем, что хеширует IdempotencyMiddleware.
 */
export function serializeCreateInstancePayload(payload: Record<string, unknown>): string {
  return JSON.stringify(payload);
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
 * сборки payload и ДО labReportingApi.createInstance().
 */
export function resolveCreateInstanceIdempotencyKey(payload: Record<string, unknown>): string {
  const slot = storageSlotId(buildCreateInstanceSlotKey(payload));
  const snapshot = serializeCreateInstancePayload(payload);
  const stored = readStoredKey(slot);
  // proceed: тот же payload, исход прошлой попытки неизвестен — тот же ключ,
  // backend вернёт закоммиченный бланк вместо второго INSERT.
  if (stored && stored.payload === snapshot) {
    return stored.key;
  }
  // bind (слота нет) / rotate (payload изменился — другая логическая
  // операция): свежий ключ и свежий снимок.
  const key = generateCreateInstanceOperationId();
  writeStoredKey(slot, { key, payload: snapshot });
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
 * ключ с неопределённым исходом (и каким payload-снимком он связан).
 */
export function peekCreateInstanceIdempotencyKey(
  payload: Record<string, unknown>,
): StoredCreateInstanceKey | null {
  return readStoredKey(storageSlotId(buildCreateInstanceSlotKey(payload)));
}
