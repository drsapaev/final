import { toast } from 'react-toastify';

/**
 * STRAT#2: useLabToast — единая точка для всех лабораторных нотификаций.
 *
 * Ранее в lab-модуле было 3 канала нотификаций:
 *   1. `notify(severity, message)` callback prop (42 calls) — основной канал
 *      для success/error/info от операций (save, finalize, notify patient).
 *   2. `toast` из react-toastify (3 calls в LabReportWorkbench) — для
 *      numeric validation с расширенными опциями (autoClose, onClick undo).
 *   3. `notifyService` из services/notify (2 calls в LabPanel) — для
 *      session-expiry (отдельный домен, не затрагивается).
 *
 * Проблема: пользователь видел ошибки одновременно в 3 разных визуальных
 * зонах — красный Alert сверху, toast справа-сверху, всплывающее
 * уведомление по центру. Когнитивная нагрузка x3.
 *
 * Решение: единый хук useLabToast, который:
 *   - Для простых сообщений (success/error/info/warning без опций)
 *     делегирует в `notify` callback (parent-owned, inline Alert).
 *   - Для interactive toasts (с onClick, custom autoClose) использует
 *     `toast` напрямую — это legitimate use case, который не покрывается
 *     простым notify.
 *
 * Соответствует Nielsen Heuristic #4 (Consistency & Standards).
 *
 * Usage:
 *   const labToast = useLabToast(notify);
 *   labToast.success('Сохранено');           // → notify('success', 'Сохранено')
 *   labToast.error('Ошибка');                 // → notify('error', 'Ошибка')
 *   labToast.interactiveError('Некорректно', { onClick: undo, autoClose: 6000 });
 *
 * Migration path: постепенно заменяем прямые toast.* вызовы на
 * labToast.interactive* там, где нужен onClick. Когда все calls будут
 * migrated, можно будет добавить единый toast container и убрать
 * react-toastify dependency (если полностью перейдём на inline alerts).
 */
export function useLabToast(notify) {
  return {
    // Простые сообщения — делегируем в notify callback.
    success: (message) => notify('success', message),
    error: (message) => notify('error', message),
    info: (message) => notify('info', message),
    warning: (message) => notify('warning', message),

    // Interactive toasts — используем toast напрямую для backward compat.
    // Эти методы сохраняются для случаев, где нужен onClick/autoClose.
    // Постепенно migrated на обычные success/error когда UI упрощается.
    interactiveError: (message, options = {}) => toast.error(message, options),
    interactiveWarning: (message, options = {}) => toast.warning(message, options),
    interactiveInfo: (message, options = {}) => toast.info(message, options),
  };
}
