/**
 * PR-UI-14-6: cashier history-table sort state (verbatim move from
 * CashierPanel — UX Audit #4.2 client-side sort).
 *
 * Sorting applies to already-loaded grouped payments
 * (after groupPaymentsByPatientAndTime). Supported fields:
 * 'date' | 'patient' | 'amount'.
 */

import { useState } from 'react';

import type { CashierSortField, CashierSortDir } from './cashierPaymentRows';

export const useCashierSort = () => {
  const [sortField, setSortField] = useState<CashierSortField>('date');
  const [sortDir, setSortDir] = useState<CashierSortDir>('desc'); // 'asc' | 'desc'

  const toggleSort = (field: CashierSortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  return {
    sortField,
    sortDir,
    toggleSort,
  };
};
