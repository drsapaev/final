/**
 * PR 3351 (review round 7, P1): два независимых уровня pending-защиты.
 *
 * Round 6 закрыл pending-only операции (clone/finalize/print) от
 * refresh/закрытия вкладки/ухода с /lab, но report CREATE остался вне
 * защиты: его неидемпотентный POST /lab/report-instances намеренно не
 * попадал в общий pending-статус, чтобы сохранить latest-wins семантику
 * для переключения контекста внутри панели. Разделение уровней возвращает
 * CREATE под защиту документа, не ломая latest-wins:
 *
 *   blocksContextTransition — контекстные переходы внутри LabPanel
 *     (смена пациента/отчёта/шаблона, Escape, urlIntent). CREATE =
 *     latest-wins: поздний ответ отбрасывается по operation-context
 *     (epoch/selectionKey/patientId), переход не ждёт POST;
 *
 *   blocksDocumentLeave — полный уход с /lab: refresh/закрытие вкладки
 *     (beforeunload), SPA route-leave (Header/Profile/Command Palette/
 *     logout), browser Back (sentinel) и session-expiry redirect.
 *     Здесь CREATE блокирует наравне с остальными операциями: потеря
 *     ответа неидемпотентного POST заставляет оператора повторять
 *     создание и плодит дубли бланков.
 *
 * null от workbench-а (cleanup эффекта) снимает источник с обоих
 * уровней разом.
 */

export interface LabOperationPendingState {
  /** Операция блокирует контекстные переходы своей области (sourceIds). */
  blocksContextTransition: boolean;
  /**
   * Операция блокирует полный уход с /lab: beforeunload, route-leave,
   * sentinel (browser Back), session-expiry redirect.
   */
  blocksDocumentLeave: boolean;
}

/** Все операции шаблона (create/save/clone/archive) блокируют оба уровня. */
export const LAB_OPERATION_PENDING_ALL: LabOperationPendingState = {
  blocksContextTransition: true,
  blocksDocumentLeave: true,
};

/** Операция завершена — источник снимается с обоих уровней. */
export const LAB_OPERATION_PENDING_NONE: LabOperationPendingState = {
  blocksContextTransition: false,
  blocksDocumentLeave: false,
};
