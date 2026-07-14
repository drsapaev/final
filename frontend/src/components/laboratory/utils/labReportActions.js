/**
 * P-04 fix: helper-функции для работы с actions state machine бланка.
 *
 * LAB_REPORT_ACTION_CAN_FIELD — маппинг имени действия в boolean-флаг
 * на instance (например, 'finalize' → 'can_finalize'). Используется
 * как fallback, если available_actions не пришёл с backend.
 *
 * hasLabReportAction — проверяет, доступно ли действие для instance.
 * Приоритет: available_actions (server-driven) > can_* flags (legacy).
 *
 * flagVariant — определяет визуальный variant Badge по флагу и severity.
 */

export const LAB_REPORT_ACTION_CAN_FIELD = {
  edit: 'can_edit',
  save_draft: 'can_save_draft',
  // L-H-2 fix: mark_ready удалён — UI-кнопка убрана в WF-round5.
  // Если backend вернёт can_mark_ready в available_actions, фронт его
  // проигнорирует (нет UI-действия). Чтобы вернуть — добавить UI + тесты.
  finalize: 'can_finalize',
  revise: 'can_revise',
  print: 'can_print'
};

export function hasLabReportAction(instance, action) {
  const normalizedAction = String(action || '').trim().toLowerCase();
  if (!instance || !normalizedAction) {
    return false;
  }

  if (Array.isArray(instance.available_actions)) {
    return instance.available_actions.some(
      (availableAction) => String(availableAction || '').trim().toLowerCase() === normalizedAction
    );
  }

  const canField = LAB_REPORT_ACTION_CAN_FIELD[normalizedAction];
  if (canField && Object.prototype.hasOwnProperty.call(instance, canField)) {
    return Boolean(instance[canField]);
  }

  return false;
}

export function flagVariant(flag, severity = null) {
  if (severity !== null && severity >= 300) {
    return 'danger';
  }
  if (flag === 'high' || flag === 'warning' || flag === 'abnormal') {
    return 'warning';
  }
  if (flag === 'low') {
    return 'primary';
  }
  return 'info';
}
