/**
 * PR-UI-09e-2: EnhancedAppointmentsTable state lifecycle hook.
 *
 * Verbatim move from EnhancedAppointmentsTable.tsx: state declarations,
 * PR-UI-01 theme-sync effect, sort/filter/pagination memos and the
 * selection handlers. Pure sort/filter bodies live in
 * appointmentsTableContracts.ts; memo wrappers keep original deps.
 */

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import {
  type AppointmentRow,
  sortAppointmentsData,
  filterAppointmentsData,
} from './appointmentsTableContracts';

export interface UseAppointmentsTableStateParams {
  data: AppointmentRow[];
  externalSelectedRows?: Set<unknown>;
  onRowSelect?: (id: unknown, checked?: boolean) => void;
  preferCanonicalQueueNumber?: boolean;
}

export const useAppointmentsTableState = ({
  data,
  externalSelectedRows,
  onRowSelect,
  preferCanonicalQueueNumber = false,
}: UseAppointmentsTableStateParams) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [sortConfig, setSortConfig] = useState<{ key: string | null; direction: string }>({ key: null, direction: 'asc' });
  const [filterConfig, setFilterConfig] = useState({
    search: '',
    status: '',
    dateFrom: '',
    dateTo: '',
    doctor: '',
    department: ''
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(20);
  // Используем внешнее состояние, если передано, иначе внутреннее
  const [internalSelectedRows, setInternalSelectedRows] = useState(new Set());
  const selectedRows = externalSelectedRows || internalSelectedRows;

  // PR-UI-01: read colorScheme from useTheme() and apply it directly to the
  // table container. Previously the effect read from localStorage, but the
  // parent ThemeProvider's passive effect (ThemeContext.tsx:330-337) persists
  // to localStorage AFTER child effects run - so reading localStorage gave
  // stale values on the same render cycle. Using the context value directly
  // eliminates the race condition (per Codex review feedback).
  const { colorScheme: themeColorScheme } = useTheme();

  // Локально дублируем активную схему на контейнер таблицы, чтобы CSS [data-color-scheme]
  // сработал даже при временной потере атрибута на <html>
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    // PR-UI-01: derive attribute directly from context value (not localStorage).
    // Custom schemes are vibrant/glass/gradient (kind === 'custom' in colorScheme.ts).
    // Standard schemes are light/dark/auto - no data-color-scheme attribute needed
    // (CSS :root handles them via prefers-color-scheme media queries).
    const customSchemes = ['vibrant', 'glass', 'gradient'];
    if (customSchemes.includes(themeColorScheme)) {
      el.setAttribute('data-color-scheme', themeColorScheme);
    } else {
      el.removeAttribute('data-color-scheme');
    }
  }, [themeColorScheme]);

  // Сортировка данных
  const sortedData = useMemo(() => {
    return sortAppointmentsData(data, sortConfig, preferCanonicalQueueNumber);
  }, [data, sortConfig, preferCanonicalQueueNumber]);

  // Фильтрация данных
  const filteredData = useMemo(() => {
    return filterAppointmentsData(sortedData, filterConfig);
  }, [sortedData, filterConfig]);

  // REG-FE-051 (audit ledger 3803): смена фильтра — новая выборка, пользователь
  // возвращается на первую страницу (стр. 3 при двух совпадениях раньше
  // рисовала «пустую таблицу», скрывая совпавшие записи).
  const filterSignature = `${filterConfig.search}|${filterConfig.status}|${filterConfig.dateFrom}|${filterConfig.dateTo}|${filterConfig.doctor}|${filterConfig.department}`;
  const lastFilterSignatureRef = useRef(filterSignature);
  useEffect(() => {
    if (lastFilterSignatureRef.current !== filterSignature) {
      lastFilterSignatureRef.current = filterSignature;
      setCurrentPage(1);
    }
  }, [filterSignature]);

  const totalPages = Math.max(1, Math.ceil(filteredData.length / pageSize));
  // REG-FE-051: данные сократились (refresh/фильтр) — страница зажимается в
  // диапазон, чтобы таблица никогда не показывала пустую страницу вместо
  // существующих совпадений.
  const effectiveCurrentPage = Math.min(currentPage, totalPages);

  // Пагинация
  const paginatedData = useMemo(() => {
    const start = (effectiveCurrentPage - 1) * pageSize;
    return filteredData.slice(start, start + pageSize);
  }, [filteredData, effectiveCurrentPage, pageSize]);

  // Обработчик сортировки
  const handleSort = useCallback((key: string) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  }, []);

  // Обработчик выбора строк
  const handleRowSelect = useCallback((id: string | number, checked: boolean) => {
    if (onRowSelect) {
      // Используем внешний обработчик
      onRowSelect(id, checked);
    } else {
      // Используем внутреннее состояние
      setInternalSelectedRows((prev) => {
        const newSet = new Set(prev);
        if (checked) {
          newSet.add(id);
        } else {
          newSet.delete(id);
        }
        return newSet;
      });
    }
  }, [onRowSelect]);

  // Обработчик выбора всех строк
  const handleSelectAll = useCallback((checked: boolean) => {
    if (onRowSelect) {
      // Используем внешний обработчик для каждой строки
      paginatedData.forEach((row: AppointmentRow) => {
        onRowSelect(row.id, checked);
      });
    } else {
      // Используем внутреннее состояние
      if (checked) {
        setInternalSelectedRows(new Set(paginatedData.map((row: AppointmentRow) => row.id)));
      } else {
        setInternalSelectedRows(new Set());
      }
    }
  }, [paginatedData, onRowSelect]);

  return {
    containerRef,
    filterConfig,
    setFilterConfig,
    // REG-FE-051: наружу отдаётся зажатая страница — селектор пагинации
    // показывает реальную текущую страницу, а не зависшее значение.
    currentPage: effectiveCurrentPage,
    setCurrentPage,
    filteredData,
    paginatedData,
    totalPages,
    selectedRows,
    handleSort,
    handleRowSelect,
    handleSelectAll,
  };
};
