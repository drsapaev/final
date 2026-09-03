/**
 * PR-UI-14-6: cashier filter state (verbatim move from CashierPanel).
 *
 * Owns the history-tab status filter and the date-filter slice
 * (single-day mode + range mode). The worklist data hook consumes these
 * values to compute request date params.
 */

import { useState } from 'react';

import { getLocalDateString } from './cashierPaymentContracts';

export const useCashierFilters = () => {
  const [status, setStatus] = useState('all');

  // Состояния для календаря
  const [dateMode, setDateMode] = useState('single'); // 'single' | 'range'
  const [selectedDate, setSelectedDate] = useState(() => getLocalDateString());
  const [dateFrom, setDateFrom] = useState(() => getLocalDateString());
  const [dateTo, setDateTo] = useState(() => getLocalDateString());

  return {
    status,
    setStatus,
    dateMode,
    setDateMode,
    selectedDate,
    setSelectedDate,
    dateFrom,
    setDateFrom,
    dateTo,
    setDateTo,
  };
};
