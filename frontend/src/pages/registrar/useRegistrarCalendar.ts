/**
 * Registrar Panel — worklist calendar state hook.
 *
 * PR-UI-13-5: extracted from RegistrarPanel.tsx — the calendar date-selection
 * slice for the worklist (history mode):
 * - showCalendar: calendar mode flag (historyDate wins over the URL date —
 *   see useRegistrarWorklistData)
 * - historyDate: the calendar-selected date
 * - tempDateInput: the inline date input draft (synced from historyDate when
 *   the calendar opens; applied on blur/native change in WelcomeView)
 * - the sync effect + the R-1.3 rationale (debounce removed: date applies on
 *   blur or native onChange — no dead second)
 */
import { useEffect, useState } from 'react';
import { getLocalDateString } from '../../utils/dateUtils';

export const useRegistrarCalendar = () => {
  const [showCalendar, setShowCalendar] = useState(false);
  const [historyDate, setHistoryDate] = useState(getLocalDateString());
  const [tempDateInput, setTempDateInput] = useState(getLocalDateString()); // Выбор врача остаётся явным: URL-параметр или ручной выбор в очереди

  // Синхронизация tempDateInput с historyDate при открытии календаря
  useEffect(() => {
    if (showCalendar) {
      setTempDateInput(historyDate);
    }
  }, [showCalendar, historyDate]);

  // UX Audit R-1.3: debounce 1000ms удалён.
  // Раньше: setTimeout 1s + onBlur дублировали применение даты, создавая
  // «мёртвую» секунду без визуального отклика (Nielsen #2).
  // Теперь: дата применяется только через onBlur в WelcomeView (стандартный
  // паттерн для date-picker'ов) или через нативный onChange календаря.

  return {
    showCalendar,
    setShowCalendar,
    historyDate,
    setHistoryDate,
    tempDateInput,
    setTempDateInput,
  };
};

export default useRegistrarCalendar;
